"""U6.3 VoiceTurn-to-real-TTS bridge.

Opt-in only. No paid provider is activated here.
"""

from dataclasses import dataclass

from . import service as voice_service
from .models import VoiceTurn
from .real_tts_integration import execute_isolated_live_tts
from .real_audio_recovery import recover_real_voice_audio


class RealVoiceBridgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class RealVoiceBridgeResult:
    state: str
    request_id: object
    audio_available: bool


def execute_real_voice_bridge(
    *,
    user,
    session_id,
    request_id,
    audio_store,
    synthesize,
):
    if audio_store is None:
        raise RealVoiceBridgeError("audio_store_required")

    if not callable(synthesize):
        raise RealVoiceBridgeError("synthesizer_required")

    turn, claimed = voice_service.claim_tts_dispatch(
        user=user,
        session_id=session_id,
        request_id=request_id,
    )

    if not claimed:
        return RealVoiceBridgeResult(
            state=str(turn.state),
            request_id=turn.request_id,
            audio_available=False,
        )

    session = turn.session

    def deadline_checked_synthesize(text):
        voice_service._session(user, session_id)
        return synthesize(text)

    voice_service._session(user, session_id)
    result = execute_isolated_live_tts(
        user=user,
        assistant_id=session.assistant_id,
        conversation_id=session.conversation.public_id,
        message_id=turn.assistant_message_id,
        request_id=turn.request_id,
        audio_store=audio_store,
        synthesize=deadline_checked_synthesize,
    )

    if result.state == "succeeded":
        # A provider success alone is not enough.
        # Recovery must verify the saved TTS request and
        # retrieve a valid MP3 before completing VoiceTurn.
        recovered = recover_real_voice_audio(
            user=user,
            session_id=session.public_id,
            request_id=turn.request_id,
            audio_store=audio_store,
        )

        if recovered.audio_available:
            return RealVoiceBridgeResult(
                state=VoiceTurn.State.COMPLETED,
                request_id=turn.request_id,
                audio_available=True,
            )

        return RealVoiceBridgeResult(
            state=VoiceTurn.State.SYNTHESIZING,
            request_id=turn.request_id,
            audio_available=False,
        )

    # No automatic retry for dispatched/uncertain requests.
    return RealVoiceBridgeResult(
        state=result.state,
        request_id=result.request_id,
        audio_available=False,
    )
