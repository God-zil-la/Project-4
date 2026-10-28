"""U6.3 validation of generated MP3 audio."""

from ai_assistant.tts.audio_storage import MAX_AUDIO_BYTES


def validate_live_mp3(audio):
    if not isinstance(audio, bytes):
        raise ValueError("invalid_mp3_type")

    if not 0 < len(audio) <= MAX_AUDIO_BYTES:
        raise ValueError("invalid_mp3_size")

    id3 = audio.startswith(b"ID3")

    frame = (
        len(audio) >= 4
        and audio[0] == 0xFF
        and (audio[1] & 0xE0) == 0xE0
        and (audio[1] & 0x06) != 0
        and (audio[2] & 0xF0) != 0xF0
    )

    if not (id3 or frame):
        raise ValueError("invalid_mp3_header")

    return audio
