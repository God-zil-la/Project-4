"""Transactional preparation of TTS requests for saved assistant responses."""

from . import service
from .errors import Conflict
from .message_access import get_assistant_message
from .message_identity import validate_saved_response
from .models import TTSRequest


@service.atomic
def prepare_saved_response(*, user, assistant_id, conversation_id, message_id, request_id):
    """Bind one request key to one authorized, saved assistant message."""

    text = get_assistant_message(
        user=user,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )

    key, fingerprint = validate_saved_response(
        text=text,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )

    user_id = service.authorize(user, assistant_id)
    account = service.lock_account(user_id)
    service.authorize(user, assistant_id)  # Recheck after lock wait.

    # Re-read and revalidate after waiting for the account lock.
    current_text = get_assistant_message(
        user=user,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )

    _, current_fingerprint = validate_saved_response(
        text=current_text,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )

    if current_fingerprint != fingerprint:
        raise Conflict('message_changed')

    row = TTSRequest.objects.filter(
        account=account,
        request_id=key,
    ).first()

    if row:
        if row.fingerprint != fingerprint or row.assistant_id != assistant_id:
            raise Conflict('request_key_reused')
        return row

    return TTSRequest.objects.create(
        account=account,
        assistant_id=assistant_id,
        request_id=key,
        fingerprint=fingerprint,
    )
