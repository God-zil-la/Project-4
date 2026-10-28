"""Opt-in, private TTS AudioStore backed by a durable cleanup reservation.

Construction is explicit. This module never opens R2 or creates tables on import.
The caller supplies a configured R2AudioStore and PostgresAudioRepository.
"""

from datetime import datetime, timezone
from uuid import UUID

from .audio_storage import AUDIO_TTL, validate_audio
from .models import TTSRequest


class DurableR2AudioStore:
    def __init__(self, *, repository, r2_store, user_id):
        if type(user_id) is not int or user_id <= 0:
            raise ValueError('invalid_user_id')
        self.repository = repository
        self.r2_store = r2_store
        self.user_id = user_id

    def _request(self, request_id):
        if not isinstance(request_id, UUID):
            raise ValueError('invalid_request_id')
        row = (
            TTSRequest.objects.select_related('account')
            .filter(pk=request_id, account__user_id=self.user_id)
            .first()
        )
        if row is None:
            raise ValueError('tts_request_not_owned')
        if row.created_at.tzinfo is None or row.created_at.utcoffset() is None:
            raise ValueError('invalid_request_creation_time')
        return row

    def save(self, *, request_id, audio):
        validate_audio(audio)
        row = self._request(request_id)
        if row.state not in ('dispatched', 'uncertain', 'succeeded'):
            raise ValueError('tts_request_not_dispatched')
        # Immutable deadline: anchored to the server-created request row.
        expires_at = row.created_at + AUDIO_TTL
        if datetime.now(timezone.utc) >= expires_at:
            raise ValueError('tts_audio_expired')
        # This commits before any R2 network I/O. Fail closed on DB errors.
        self.repository.reserve(
            request_id=request_id,
            account_id=row.account_id,
            size_bytes=len(audio),
            expires_at=expires_at,
        )
        # On an exact retry, reserve() returns False; writing again is safe
        # only because R2 uses create-if-absent and verifies existing bytes.
        self.r2_store.save(
            request_id=request_id,
            audio=audio,
            expires_at=expires_at,
        )

    def load(self, *, request_id):
        row = self._request(request_id)
        if datetime.now(timezone.utc) >= row.created_at + AUDIO_TTL:
            return None
        return self.r2_store.load(
            request_id=request_id, expected_expiry=row.created_at + AUDIO_TTL,
        )

    def delete(self, *, request_id):
        # This per-user wrapper is not the cleanup worker's deletion adapter.
        # Cleanup must use the raw R2 store, as owner rows may be deleted.
        self._request(request_id)
        return self.r2_store.delete(request_id=request_id)
