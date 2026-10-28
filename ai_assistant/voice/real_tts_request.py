"""Prepare identity-bound real TTS requests for U6.3."""

from ai_assistant.tts import service
from ai_assistant.tts.errors import Conflict
from ai_assistant.tts.message_access import get_assistant_message
from ai_assistant.tts.models import TTSRequest

from .real_tts_identity import validate_real_tts_identity


@service.atomic
def prepare_real_tts_request(
    *,
    user,
    assistant_id,
    conversation_id,
    message_id,
    request_id,
):
    text = get_assistant_message(
        user=user,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )

    key, fingerprint = validate_real_tts_identity(
        text=text,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )

    user_id = service.authorize(user, assistant_id)
    account = service.lock_account(user_id)

    service.authorize(user, assistant_id)

    current_text = get_assistant_message(
        user=user,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )

    _, current_fingerprint = validate_real_tts_identity(
        text=current_text,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )

    if current_fingerprint != fingerprint:
        raise Conflict("message_changed")

    row = TTSRequest.objects.filter(
        account=account,
        request_id=key,
    ).first()

    if row is not None:
        if (
            row.fingerprint != fingerprint
            or row.assistant_id != assistant_id
        ):
            raise Conflict("request_key_reused")
        return row

    return TTSRequest.objects.create(
        account=account,
        assistant_id=assistant_id,
        request_id=key,
        fingerprint=fingerprint,
    )
