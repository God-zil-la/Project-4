"""Signed, expiring state for Premium Discord guild authorization.

This module does not authorize a guild by itself: the callback MUST exchange
the OAuth code with Discord and verify the account's guild permissions before
persisting an installation. No existing Pro/U5 routes are modified.
"""
from django.core import signing
from django.core.exceptions import ValidationError

STATE_SALT = "ai-assistant.premium-discord.oauth-state.v1"
STATE_MAX_AGE_SECONDS = 600


def create_oauth_state(user_id):
    """Bind a short-lived OAuth callback to the logged-in account."""
    if isinstance(user_id, bool) or not str(user_id).isdigit() or int(user_id) <= 0:
        raise ValueError("Invalid account ID.")
    return signing.dumps({"uid": int(user_id)}, salt=STATE_SALT, compress=True)


def validate_oauth_state(state, authenticated_user_id):
    """Fail closed if the state is forged, expired, or belongs to another user."""
    if not isinstance(state, str) or not state or len(state) > 4096:
        raise ValidationError("Invalid Discord authorization state.")
    try:
        data = signing.loads(state, salt=STATE_SALT, max_age=STATE_MAX_AGE_SECONDS)
    except (signing.BadSignature, signing.SignatureExpired, TypeError, ValueError) as exc:
        raise ValidationError("Invalid or expired Discord authorization state.") from exc
    if (
        not isinstance(data, dict)
        or isinstance(data.get("uid"), bool)
        or not isinstance(data.get("uid"), int)
        or data["uid"] <= 0
        or isinstance(authenticated_user_id, bool)
        or data["uid"] != authenticated_user_id
    ):
        raise ValidationError("Discord authorization does not match this account.")
    return data["uid"]
