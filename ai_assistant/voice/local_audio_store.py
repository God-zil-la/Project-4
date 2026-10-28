"""Private, bounded, local MP3 storage for U6.3 development."""

import os
import tempfile
import time
from pathlib import Path

from django.conf import settings

from ai_assistant.tts.audio_storage import AUDIO_TTL, MAX_AUDIO_BYTES

from .mp3_validation import validate_live_mp3


class LocalVoiceAudioStore:
    """Owner-scoped storage keyed by internal TTSRequest IDs."""

    def __init__(self, *, user_id):
        if type(user_id) is not int or user_id <= 0:
            raise ValueError("invalid_user_id")

        self.user_id = user_id
        self.root = (
            Path(settings.BASE_DIR)
            / ".u63_private_audio"
            / str(user_id)
        )

    def _path(self, request_id):
        from uuid import UUID

        if type(request_id) is not UUID:
            raise ValueError("invalid_audio_request_id")

        return self.root / f"{request_id}.mp3"

    def save(self, *, request_id, audio):
        audio = validate_live_mp3(audio)
        destination = self._path(request_id)

        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

        temporary = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=".u63_",
                suffix=".tmp",
                dir=self.root,
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(audio)
                handle.flush()
                os.fsync(handle.fileno())

            # Exclusive, atomic publication via hard link.
            # Never overwrite a previously saved request.
            os.link(temporary, destination)

        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def load(self, *, request_id):
        path = self._path(request_id)

        try:
            stat = path.stat()

            if stat.st_size <= 0 or stat.st_size > MAX_AUDIO_BYTES:
                return None

            if time.time() - stat.st_mtime > AUDIO_TTL.total_seconds():
                return None

            audio = path.read_bytes()
            return validate_live_mp3(audio)

        except (FileNotFoundError, OSError, ValueError):
            return None
