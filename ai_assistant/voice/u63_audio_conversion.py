"""
U6.3 mobile audio conversion.

Isolated conversion utility.
Does not modify U6.1 or U6.2.
Does not call STT, AI or TTS.
"""

import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path


MAX_INPUT_BYTES = 10 * 1024 * 1024
MAX_OUTPUT_BYTES = 10 * 1024 * 1024
MAX_DURATION_SECONDS = 60
CONVERSION_TIMEOUT_SECONDS = 20


class U63AudioConversionError(ValueError):
    pass


def _require_executable(name):
    executable = shutil.which(name)
    if not executable:
        raise U63AudioConversionError(
            f"Required audio executable unavailable: {name}"
        )
    return executable


def _run(command):
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=CONVERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise U63AudioConversionError(
            "Audio conversion timed out"
        ) from exc

    if result.returncode != 0:
        raise U63AudioConversionError(
            "Audio processing failed"
        )

    return result.stdout


def _validate_input(data):
    if not isinstance(data, bytes):
        raise U63AudioConversionError(
            "Audio input must be bytes"
        )

    if not 0 < len(data) <= MAX_INPUT_BYTES:
        raise U63AudioConversionError(
            "Audio input exceeds permitted size"
        )

    # MP4/M4A file type box.
    if len(data) < 12 or data[4:8] != b"ftyp":
        raise U63AudioConversionError(
            "Input is not an MP4/M4A container"
        )


def _probe_audio(ffprobe, source):
    import json

    output = _run([
        ffprobe,
        "-v", "error",
        "-select_streams", "a:0",
        "-show_entries",
        "stream=codec_name:format=duration",
        "-of", "json",
        str(source),
    ])

    try:
        metadata = json.loads(output)
        streams = metadata.get("streams") or []
        duration = float(
            (metadata.get("format") or {}).get("duration") or 0
        )
    except (ValueError, TypeError) as exc:
        raise U63AudioConversionError(
            "Invalid audio metadata"
        ) from exc

    if not streams or streams[0].get("codec_name") != "aac":
        raise U63AudioConversionError(
            "Only AAC audio is accepted"
        )

    if not 0 < duration <= MAX_DURATION_SECONDS:
        raise U63AudioConversionError(
            "Audio duration outside permitted range"
        )


def convert_mobile_aac_to_wav(data):
    """
    Convert M4A/MP4 AAC bytes into genuine PCM WAV bytes.

    No network calls.
    No paid provider calls.
    """

    _validate_input(data)

    ffmpeg = _require_executable("ffmpeg")
    ffprobe = _require_executable("ffprobe")

    with tempfile.TemporaryDirectory(
        prefix="u63_audio_"
    ) as directory:
        root = Path(directory)
        source = root / "input.m4a"
        output = root / "output.wav"

        source.write_bytes(data)

        _probe_audio(ffprobe, source)

        _run([
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel", "error",
            "-y",
            "-threads", "1",
            "-filter_threads", "1",
            "-i", str(source),
            "-map", "0:a:0",
            "-vn",
            "-ac", "1",
            "-ar", "16000",
            "-c:a", "pcm_s16le",
            "-t", str(MAX_DURATION_SECONDS),
            str(output),
        ])

        if not output.is_file():
            raise U63AudioConversionError(
                "WAV output missing"
            )

        if not 44 <= output.stat().st_size <= MAX_OUTPUT_BYTES:
            raise U63AudioConversionError(
                "WAV output size invalid"
            )

        with wave.open(str(output), "rb") as wav:
            if (
                wav.getnchannels() != 1
                or wav.getsampwidth() != 2
                or wav.getframerate() != 16000
                or wav.getnframes() == 0
            ):
                raise U63AudioConversionError(
                    "Converted WAV format invalid"
                )

        return output.read_bytes()