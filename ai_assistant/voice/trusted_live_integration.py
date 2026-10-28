"""Trusted, explicitly injected U6.3 Live Voice integration.

No public endpoint, automatic provider activation, or billing changes.
"""

from .live_pipeline import execute_live_voice_turn
from .service import VoiceConflict


def execute_trusted_live_voice(
    *,
    user,
    session_id,
    request_id,
    reservation,
    evidence,
    audio,
    transcriber,
    audio_store=None,
    real_tts_synthesize=None,
):
    """Run the existing pipeline using trusted server-side dependencies."""

    if not callable(transcriber):
        raise VoiceConflict("Trusted transcriber required.")

    if real_tts_synthesize is not None and not callable(
        real_tts_synthesize
    ):
        raise VoiceConflict("Invalid TTS synthesizer.")

    return execute_live_voice_turn(
        user=user,
        session_id=session_id,
        request_id=request_id,
        reservation=reservation,
        evidence=evidence,
        audio=audio,
        transcriber=transcriber,
        audio_store=audio_store,
        real_tts_synthesize=real_tts_synthesize,
    )