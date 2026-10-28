"""U6.3 bridge to existing U6.2 saved-answer synthesis."""

from ai_assistant.tts.saved_synthesis import (
    synthesize_saved_response,
    recover_saved_response,
)

from .models import VoiceTurn
from .service import (
    VoiceAccessDenied,
    VoiceConflict,
    _session,
    _uuid,
    claim_tts_dispatch,
)


def _saved_turn(*, user, session_id, request_id):
    session = _session(user, session_id)

    turn = VoiceTurn.objects.filter(
        session=session,
        request_id=_uuid(request_id),
    ).first()

    if turn is None:
        raise VoiceAccessDenied("Voice turn not found.")

    if turn.assistant_message_id is None:
        raise VoiceConflict("AI answer has not been saved.")

    return session, turn


def _finish_tts(*, user, session, turn, result):
    from .service import advance_turn

    state = getattr(result, "state", None)

    if state == "succeeded":
        target = VoiceTurn.State.COMPLETED
    elif state == "not_processed":
        target = VoiceTurn.State.FAILED
    else:
        target = VoiceTurn.State.UNCERTAIN

    advance_turn(
        user=user,
        session_id=session.public_id,
        request_id=turn.request_id,
        expected=VoiceTurn.State.SYNTHESIZING,
        target=target,
    )

    return result


def synthesize_voice_answer(*, user, session_id, request_id, audio_store=None):
    session, turn = _saved_turn(
        user=user,
        session_id=session_id,
        request_id=request_id,
    )

    turn, claimed = claim_tts_dispatch(
        user=user,
        session_id=session.public_id,
        request_id=turn.request_id,
    )

    if not claimed:
        raise VoiceConflict(
            "TTS already dispatched; use recovery instead."
        )

    try:
        _session(user, session_id)
        result = synthesize_saved_response(
            user=user,
            assistant_id=session.assistant_id,
            conversation_id=session.conversation.public_id,
            message_id=turn.assistant_message_id,
            request_id=turn.request_id,
            audio_store=audio_store,
        )
    except Exception:
        # Preserve SYNTHESIZING after an uncertain failure.
        # Never retry the provider automatically.
        raise

    return _finish_tts(
        user=user,
        session=session,
        turn=turn,
        result=result,
    )


def recover_voice_answer(*, user, session_id, request_id, audio_store):
    session, turn = _saved_turn(
        user=user,
        session_id=session_id,
        request_id=request_id,
    )

    if turn.state not in {
        VoiceTurn.State.SYNTHESIZING,
        VoiceTurn.State.COMPLETED,
        VoiceTurn.State.UNCERTAIN,
    }:
        raise VoiceConflict("TTS recovery not available.")

    result = recover_saved_response(
        user=user,
        assistant_id=session.assistant_id,
        conversation_id=session.conversation.public_id,
        message_id=turn.assistant_message_id,
        request_id=turn.request_id,
        audio_store=audio_store,
    )

    if getattr(result, "state", None) == "succeeded":
        from django.db import transaction

        with transaction.atomic():
            locked = VoiceTurn.objects.select_for_update().get(pk=turn.pk)

            if locked.state in {
                VoiceTurn.State.SYNTHESIZING,
                VoiceTurn.State.UNCERTAIN,
            }:
                locked.state = VoiceTurn.State.COMPLETED
                locked.save(update_fields=["state", "updated_at"])

    return result
