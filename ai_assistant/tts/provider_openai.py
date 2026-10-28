"""Optional OpenAI TTS adapter. Disabled unless explicitly enabled."""
import os
import httpx

from .errors import TTSError


class OpenAITTSProvider:
    MODEL = "tts-1"
    VOICE = "alloy"
    FORMAT = "mp3"
    URL = "https://api.openai.com/v1/audio/speech"
    MAX_AUDIO_BYTES = 8 * 1024 * 1024

    def __init__(self, *, allow_paid_calls=False):
        self.allow_paid_calls = allow_paid_calls

    def synthesize(self, text):
        if not self.allow_paid_calls or os.getenv("U62_REAL_TTS_ENABLED") != "true":
            raise TTSError("real_tts_disabled")

        if not isinstance(text, str) or not text or len(text) > 4000:
            raise TTSError("invalid_tts_input")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise TTSError("tts_api_key_missing")

        with httpx.Client(timeout=30.0, follow_redirects=False) as client:
            with client.stream(
                "POST",
                self.URL,
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": self.MODEL,
                    "voice": self.VOICE,
                    "input": text,
                    "response_format": self.FORMAT,
                },
            ) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                if content_type != "audio/mpeg":
                    raise TTSError("invalid_tts_content_type")
                audio = bytearray()

                for chunk in response.iter_bytes():
                    if len(audio) + len(chunk) > self.MAX_AUDIO_BYTES:
                        raise TTSError("tts_audio_too_large")
                    audio.extend(chunk)

                if not audio:
                    raise TTSError("empty_tts_audio")

                is_id3 = audio[:3] == b"ID3"
                is_mpeg_frame = (
                    len(audio) >= 4
                    and audio[0] == 0xFF
                    and (audio[1] & 0xE0) == 0xE0
                    and (audio[1] & 0x06) != 0
                    and (audio[2] & 0xF0) != 0xF0
                )
                if not (is_id3 or is_mpeg_frame):
                    raise TTSError("invalid_tts_audio")

                return bytes(audio)
