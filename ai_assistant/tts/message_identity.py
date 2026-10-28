"""Identity binding for saved assistant responses in U6.2."""
from hashlib import sha256
import json
from uuid import UUID

from .errors import InvalidInput
from .validation import validate


def validate_saved_response(*, text, assistant_id, conversation_id, message_id, request_id):
    """Bind a TTS request to the exact saved message and synthesis profile."""
    key, text_fingerprint = validate(
        text=text,
        assistant_id=assistant_id,
        request_id=request_id,
    )

    if type(message_id) is not int or message_id <= 0:
        raise InvalidInput('invalid_message_id')

    if not isinstance(conversation_id, (str, UUID)):
        raise InvalidInput('invalid_conversation_id')

    try:
        conversation = UUID(str(conversation_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidInput('invalid_conversation_id') from exc

    payload = [
        'u62-saved-response-v1',
        assistant_id,
        str(conversation),
        message_id,
        text_fingerprint,
        'mp3',
        'mock-only-v1',
    ]
    fingerprint = sha256(
        json.dumps(payload, separators=(',', ':')).encode('utf-8')
    ).hexdigest()

    return key, fingerprint
