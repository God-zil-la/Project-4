"""U6.3 bridge for completed U6.1 transcription results.

This module never dispatches STT provider requests or changes quotas.
Only a verified successful U6.1 reservation may supply a transcript.
"""

from ai_assistant.stt.models import STTReservation
from .models import VoiceTurn
from .service import (
    VoiceAccessDenied,
    VoiceConflict,
    _session,
    _uuid,
    save_transcript,
)


def accept_stt_result(
    *,
    user,
    session_id,
    request_id,
    reservation_id,
    transcript,
):
    """Accept an already settled STT result for the matching voice turn."""

    session = _session(user, session_id)

    turn = VoiceTurn.objects.filter(
        session=session,
        request_id=_uuid(request_id),
    ).first()

    if turn is None:
        raise VoiceAccessDenied("Voice turn not found.")

    reservation = STTReservation.objects.filter(
        pk=reservation_id,
        account__user_id=user.pk,
    ).first()

    if reservation is None:
        raise VoiceAccessDenied("STT reservation not found.")

    if (
        reservation.assistant_id != session.assistant_id
        or str(reservation.request_id) != str(turn.request_id)
        or reservation.audio_sha256 != turn.audio_sha256
    ):
        raise VoiceConflict("STT reservation does not match voice turn.")

    if reservation.state != "consumed":
        raise VoiceConflict("STT reservation is not completed.")

    return save_transcript(
        user=user,
        session_id=session.public_id,
        request_id=turn.request_id,
        transcript=transcript,
    )
