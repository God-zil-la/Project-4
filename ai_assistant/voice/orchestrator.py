"""U6.3 voice-turn orchestration after verified transcription.

External STT provider execution is intentionally handled separately.
"""

from .ai_adapter import process_voice_answer
from .real_voice_bridge import execute_real_voice_bridge
from .real_audio_recovery import recover_real_voice_audio
from .tts_adapter import synthesize_voice_answer, recover_voice_answer
from .models import VoiceTurn
from .service import (
    VoiceAccessDenied,
    VoiceConflict,
    _session,
    _uuid,
)


def continue_voice_turn(
    *,
    user,
    session_id,
    request_id,
    audio_store=None,
    real_tts_synthesize=None,
):
    """Continue a voice turn without blindly repeating provider calls."""

    session = _session(user, session_id)
    turn = VoiceTurn.objects.filter(
        session=session,
        request_id=_uuid(request_id),
    ).first()

    if turn is None:
        raise VoiceAccessDenied("Voice turn not found.")

    if turn.state == VoiceTurn.State.TRANSCRIBED:
        process_voice_answer(
            user=user,
            session_id=session.public_id,
            request_id=turn.request_id,
        )
        turn.refresh_from_db()

    if (
        real_tts_synthesize is not None
        and turn.state == VoiceTurn.State.ANSWER_SAVED
    ):
        result = execute_real_voice_bridge(
            user=user,
            session_id=session.public_id,
            request_id=turn.request_id,
            audio_store=audio_store,
            synthesize=real_tts_synthesize,
        )
        return {
            "state": result.state,
            "voice_turn_id": turn.pk,
            "assistant_message_id": turn.assistant_message_id,
            "audio": None,
            "audio_available": result.audio_available,
        }

    if turn.state == VoiceTurn.State.ANSWER_SAVED:
        result = synthesize_voice_answer(
            user=user,
            session_id=session.public_id,
            request_id=turn.request_id,
            audio_store=audio_store,
        )
        return {
            "state": getattr(result, "state", None),
            "voice_turn_id": turn.pk,
            "assistant_message_id": turn.assistant_message_id,
            "audio": getattr(result, "audio", None),
        }

    if (
        real_tts_synthesize is not None
        and turn.state in {
            VoiceTurn.State.SYNTHESIZING,
            VoiceTurn.State.COMPLETED,
            VoiceTurn.State.UNCERTAIN,
        }
        and turn.assistant_message_id is not None
    ):
        if turn.state == VoiceTurn.State.UNCERTAIN:
            return {
                "state": turn.state,
                "voice_turn_id": turn.pk,
                "assistant_message_id": turn.assistant_message_id,
                "audio": None,
                "audio_available": False,
            }

        if audio_store is None:
            raise VoiceConflict("Real audio store required.")

        recovered = recover_real_voice_audio(
            user=user,
            session_id=session.public_id,
            request_id=turn.request_id,
            audio_store=audio_store,
        )

        return {
            "state": recovered.state,
            "voice_turn_id": turn.pk,
            "assistant_message_id": turn.assistant_message_id,
            "audio": None,
            "audio_available": recovered.audio_available,
        }

    if turn.state in {
        VoiceTurn.State.SYNTHESIZING,
        VoiceTurn.State.COMPLETED,
        VoiceTurn.State.UNCERTAIN,
    } and turn.assistant_message_id is not None:
        if audio_store is None:
            return {
                "state": turn.state,
                "voice_turn_id": turn.pk,
                "assistant_message_id": turn.assistant_message_id,
                "audio": None,
            }

        result = recover_voice_answer(
            user=user,
            session_id=session.public_id,
            request_id=turn.request_id,
            audio_store=audio_store,
        )
        return {
            "state": getattr(result, "state", None),
            "voice_turn_id": turn.pk,
            "assistant_message_id": turn.assistant_message_id,
            "audio": getattr(result, "audio", None),
        }

    raise VoiceConflict(
        "Voice turn cannot be continued automatically."
    )
