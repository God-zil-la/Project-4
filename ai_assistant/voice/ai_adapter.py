"""U6.3 bridge to the existing assistant chat service."""

from ai_assistant.bots.chat_service import process_bot_message

from .models import VoiceTurn
from .provider_guard import voice_provider_scope
from .service import (
    VoiceAccessDenied,
    VoiceConflict,
    _session,
    _uuid,
    claim_ai_dispatch,
)


def process_voice_answer(*, user, session_id, request_id):
    """Dispatch once; never blindly retry an uncertain AI operation."""

    session = _session(user, session_id)

    turn = VoiceTurn.objects.select_related(
        "assistant_message"
    ).filter(
        session=session,
        request_id=_uuid(request_id),
    ).first()

    if turn is None:
        raise VoiceAccessDenied("Voice turn not found.")

    if turn.assistant_message_id is not None:
        return {
            "status": "saved",
            "assistant_message_id": turn.assistant_message_id,
            "reused": True,
        }

    if turn.state != VoiceTurn.State.TRANSCRIBED:
        raise VoiceConflict("Voice turn is not ready for AI dispatch.")

    if not turn.transcript.strip():
        raise VoiceConflict("Voice transcript is empty.")

    turn, claimed = claim_ai_dispatch(
        user=user,
        session_id=session.public_id,
        request_id=turn.request_id,
    )

    if not claimed:
        raise VoiceConflict("AI dispatch already claimed.")

    try:
        _session(user, session_id)
        with voice_provider_scope(user=user, session_id=session_id, request_id=turn.request_id):
            result = process_bot_message(
                user=user,
                bot=session.assistant,
                message=turn.transcript,
                conversation=session.conversation.public_id,
                return_message_id=True,
                voice_turn_id=turn.pk,
            )
    except Exception:
        # PROCESSING is intentionally retained.
        # A failed provider operation may already have executed;
        # do not dispatch again automatically.
        raise

    turn.refresh_from_db()

    if turn.assistant_message_id is None:
        raise VoiceConflict("AI answer was not atomically saved.")

    return {
        "status": "saved",
        "assistant_message_id": turn.assistant_message_id,
        "reused": False,
        "result": result,
    }
