"""U6.3 adapter for existing OpenAI TTS provider.

Paid synthesis is disabled unless explicitly enabled.
"""

import os

from ai_assistant.tts.errors import TTSError
from ai_assistant.tts.provider_openai import OpenAITTSProvider

from .mp3_validation import validate_live_mp3


def synthesize_live_voice_audio(*, text, allow_paid_calls=False):
    """Generate MP3 only with explicit authorization."""

    if allow_paid_calls is not True:
        raise TTSError("u63_paid_tts_not_approved")

    if os.getenv("U63_REAL_TTS_ENABLED") != "true":
        raise TTSError("u63_real_tts_disabled")

    provider = OpenAITTSProvider(
        allow_paid_calls=True,
    )

    return validate_live_mp3(provider.synthesize(text))
