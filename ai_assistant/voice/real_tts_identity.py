"""Separate identity for real U6.3 speech synthesis."""

import hashlib
import json
from uuid import UUID


REAL_TTS_PROFILE = "u63-openai-tts1-alloy-mp3-v1"


def validate_real_tts_identity(
    *,
    text,
    assistant_id,
    conversation_id,
    message_id,
    request_id,
):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("invalid_saved_text")

    if type(assistant_id) is not int or assistant_id <= 0:
        raise ValueError("invalid_assistant_id")

    if type(message_id) is not int or message_id <= 0:
        raise ValueError("invalid_message_id")

    try:
        conversation = UUID(str(conversation_id))
        request = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("invalid_uuid") from exc

    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

    payload = [
        "u63-real-saved-response-v1",
        assistant_id,
        str(conversation),
        message_id,
        text_hash,
        "mp3",
        REAL_TTS_PROFILE,
    ]

    fingerprint = hashlib.sha256(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    return request, fingerprint
