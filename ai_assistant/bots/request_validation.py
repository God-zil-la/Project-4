"""Validate JSON shapes before coercion or side effects."""
from collections.abc import Mapping
from rest_framework.exceptions import ValidationError


def validate_request_object(data, text_fields=(), nullable_fields=()):
    if not isinstance(data, Mapping):
        raise ValidationError({"error": "Request body must be an object."})
    for field in text_fields:
        if field not in data:
            continue
        value = data[field]
        if value is None and field in nullable_fields:
            continue
        if not isinstance(value, str):
            raise ValidationError({"error": f"{field} must be text."})
    if "bot_id" in data:
        value = data["bot_id"]
        if type(value) not in (str, int) or len(str(value)) > 19:
            raise ValidationError({"error": "bot_id must be an integer identifier."})
