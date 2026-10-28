"""Bounded PCM WAV validation; never trust names, MIME types or duration fields."""
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import struct
import tempfile
import wave

MAX_BYTES = 20_000_000
MAX_SECONDS = 300


class InvalidAudio(ValueError):
    pass


@dataclass(frozen=True)
class Audio:
    file: object
    milliseconds: int
    sha256: str


def _inspect(file, size):
    # Strict RIFF traversal rejects truncated/duplicate payloads and trailing data.
    header = file.read(12)
    if (len(header) != 12 or header[:4] != b'RIFF' or header[8:] != b'WAVE'
            or struct.unpack('<I', header[4:8])[0] + 8 != size):
        raise InvalidAudio('invalid_wav')
    seen = set()
    data_size = None
    while file.tell() < size:
        chunk = file.read(8)
        if len(chunk) != 8:
            raise InvalidAudio('invalid_wav')
        kind, length = struct.unpack('<4sI', chunk)
        end = file.tell() + length + length % 2
        if end > size:
            raise InvalidAudio('truncated_wav')
        if kind in (b'fmt ', b'data'):
            if kind in seen or (kind == b'data' and b'fmt ' not in seen):
                raise InvalidAudio('invalid_wav')
            seen.add(kind)
        if kind == b'fmt ':
            if length != 16:
                raise InvalidAudio('unsupported_wav')
            encoding, channels, rate, byte_rate, alignment, bits = struct.unpack('<HHIIHH', file.read(16))
            if (encoding != 1 or channels not in (1, 2) or bits not in (8, 16, 24, 32)
                    or not 8000 <= rate <= 48000
                    or alignment != channels * bits // 8 or byte_rate != rate * alignment):
                raise InvalidAudio('unsupported_wav')
        if kind == b'data':
            data_size = length
        file.seek(end)
    if seen != {b'fmt ', b'data'} or not data_size:
        raise InvalidAudio('empty_audio')
    file.seek(0)
    try:
        with wave.open(file, 'rb') as wav:
            frame_size = wav.getnchannels() * wav.getsampwidth()
            frames = wav.getnframes()
            rate = wav.getframerate()
            if data_size % frame_size or frames > MAX_SECONDS * rate:
                raise InvalidAudio('audio_too_long_or_unaligned')
            actual = 0
            while block := wav.readframes(8192):
                actual += len(block)
            if actual != data_size:
                raise InvalidAudio('truncated_wav')
            return (frames * 1000 + rate - 1) // rate
    except (wave.Error, EOFError) as exc:
        raise InvalidAudio('invalid_wav') from exc


@contextmanager
def validated_wav(upload):
    """Accept a binary file-like upload; clean up on success and every exception.

    This first implementation deliberately supports PCM WAV only. Other formats
    require an isolated decoder with resource limits before they can be enabled.
    """
    with tempfile.TemporaryFile(mode='w+b') as file:
        size = 0
        while block := upload.read(65536):
            size += len(block)
            if size > MAX_BYTES:
                raise InvalidAudio('audio_too_large')
            file.write(block)
        file.seek(0)
        milliseconds = _inspect(file, size)
        file.seek(0)
        digest = sha256()
        while block := file.read(65536):
            digest.update(block)
        file.seek(0)
        yield Audio(file, milliseconds, digest.hexdigest())
