from hashlib import sha256
import json
import re
from uuid import UUID

from .errors import InvalidInput


def validate(*, text, assistant_id, request_id):
    if type(assistant_id) is not int or assistant_id <= 0:
        raise InvalidInput('invalid_assistant')
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise InvalidInput('invalid_text')
    try:
        encoded = text.encode('utf-8', errors='strict')
    except UnicodeError as exc:
        raise InvalidInput('invalid_text_encoding') from exc
    if len(encoded) > 16000 or any(ord(c) < 32 and c not in '\n\r\t' for c in text):
        raise InvalidInput('invalid_text')
    # No markup parser or SSML mode. Ordinary comparisons such as 2 < 3 work.
    if re.search(r'<\s*(?:/?[A-Za-z]|[!?])', text):
        raise InvalidInput('plain_text_required')
    try:
        key = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise InvalidInput('invalid_request_id') from exc
    # Exact text, including whitespace, binds the request. No silent truncation.
    digest = sha256(json.dumps([assistant_id, text, 'mp3', 'mock-only-v1'],
                              ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
    return key, digest
