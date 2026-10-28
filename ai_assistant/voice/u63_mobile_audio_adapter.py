"""
U6.3 mobile audio adapter.

Accepts supported mobile audio bytes and returns
genuine PCM WAV bytes for the existing U6.3 pipeline.

Does not invoke STT, AI or TTS.
"""

import io
import wave

from .u63_audio_conversion import (
    U63AudioConversionError,
    convert_mobile_aac_to_wav,
)


MAX_INPUT_BYTES = 10 * 1024 * 1024


class U63MobileAudioError(ValueError):
    pass


def _validate_wav(data):
    try:
        with wave.open(io.BytesIO(data), "rb") as audio:
            if (
                audio.getcomptype() != "NONE"
                or audio.getnchannels() != 1
                or audio.getsampwidth() != 2
                or audio.getframerate() != 16000
                or audio.getnframes() <= 0
                or audio.getnframes() > 16000 * 60
            ):
                raise U63MobileAudioError(
                    "Unsupported WAV format"
                )
    except (wave.Error, EOFError) as exc:
        raise U63MobileAudioError(
            "Invalid WAV audio"
        ) from exc


def normalize_u63_mobile_audio(data):
    """
    Return validated PCM WAV bytes.

    WAV input: validate and preserve.
    M4A/MP4 AAC input: convert to WAV.

    Other formats: reject.
    """

    if not isinstance(data, bytes):
        raise U63MobileAudioError(
            "Audio must be supplied as bytes"
        )

    if not 0 < len(data) <= MAX_INPUT_BYTES:
        raise U63MobileAudioError(
            "Invalid audio size"
        )

    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        _validate_wav(data)
        return data

    if len(data) >= 12 and data[4:8] == b"ftyp":
        try:
            wav_data = convert_mobile_aac_to_wav(data)
        except U63AudioConversionError as exc:
            raise U63MobileAudioError(
                "Mobile audio conversion failed"
            ) from exc

        _validate_wav(wav_data)
        return wav_data

    raise U63MobileAudioError(
        "Unsupported mobile audio container"
    )