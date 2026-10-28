"""Private, bounded storage contract for generated TTS audio."""

from dataclasses import dataclass
from datetime import timedelta

MAX_AUDIO_BYTES = 8 * 1024 * 1024
AUDIO_TTL = timedelta(minutes=15)


@dataclass(frozen=True)
class StoredAudio:
    request_id: object
    account_id: int
    assistant_id: int
    content_type: str
    expires_at: object
    size_bytes: int


def validate_audio(audio: bytes) -> None:
    if not isinstance(audio, bytes) or not audio:
        raise ValueError("invalid_audio")

    if len(audio) > MAX_AUDIO_BYTES:
        raise ValueError("audio_too_large")
