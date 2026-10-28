"""In-memory audio store for isolated U6.2 tests only."""

from datetime import timedelta

from django.utils import timezone

from .audio_storage import AUDIO_TTL, validate_audio


class MemoryAudioStore:
    """Test-only store. Not safe for production or multiple workers."""

    def __init__(self):
        self._items = {}

    def save(self, *, request_id, audio):
        validate_audio(audio)
        now = timezone.now()

        existing = self._items.get(request_id)
        if existing is not None and now < existing[1]:
            return

        self._items[request_id] = (
            bytes(audio),
            now + AUDIO_TTL,
        )

    def load(self, *, request_id):
        item = self._items.get(request_id)
        if item is None:
            return None

        audio, expires_at = item
        if timezone.now() >= expires_at:
            self._items.pop(request_id, None)
            return None

        return audio

    def delete(self, *, request_id):
        self._items.pop(request_id, None)
