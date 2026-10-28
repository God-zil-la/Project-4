"""U6.3 server-only adapter for the existing U6.1 STT client.

This module never accepts credentials from an HTTP request.
Importing or constructing the adapter never makes a provider call.
"""

import os

from ai_assistant.stt.client import transcribe
from .service import VoiceConflict


def make_real_stt_transcriber(*, allow_paid_calls=False):
    """Create a trusted transcriber only after explicit server activation."""

    if allow_paid_calls is not True:
        raise VoiceConflict("Real STT calls are not authorized.")

    if os.environ.get("U63_REAL_STT_ENABLED", "").lower() != "true":
        raise VoiceConflict("Real STT provider is disabled.")

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if not api_key:
        raise VoiceConflict("Server STT credentials are unavailable.")

    def trusted_transcriber(audio):
        return transcribe(audio, api_key=api_key)

    return trusted_transcriber
