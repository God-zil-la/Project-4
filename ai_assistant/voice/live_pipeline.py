"""U6.3 trusted internal voice pipeline.

No public endpoint and no automatic provider activation.
Subscription evidence, STT reservation, audio and transcriber
must be supplied by trusted server-side integration.
"""

from .models import VoiceTurn
from .service import VoiceConflict
from .stt_pipeline import execute_testable_stt
from .orchestrator import continue_voice_turn


def execute_live_voice_turn(
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
    """Run STT, then AI and TTS, without repeating dispatched STT."""

    stt_result = execute_testable_stt(
        user=user,
        session_id=session_id,
        request_id=request_id,
        reservation=reservation,
        evidence=evidence,
        audio=audio,
        transcriber=transcriber,
    )

    if stt_result.state != VoiceTurn.State.TRANSCRIBED:
        raise VoiceConflict(
            "STT did not complete successfully."
        )

    voice_result = continue_voice_turn(
        user=user,
        session_id=session_id,
        request_id=request_id,
        audio_store=audio_store,
        real_tts_synthesize=real_tts_synthesize,
    )

    return {
        "stt_state": stt_result.state,
        "transcript": stt_result.transcript,
        "voice": voice_result,
    }
