"""Verify Discord HTTP interactions before any processing or AI calls."""
import os
import time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class DiscordInteractionVerificationError(ValueError):
    pass


def verify_discord_interaction(*, body, signature, timestamp, now=None):
    public_key_hex = os.environ.get("PREMIUM_DISCORD_PUBLIC_KEY", "").strip()
    if not public_key_hex:
        raise DiscordInteractionVerificationError("Premium Discord public key not configured.")
    if not isinstance(body, bytes) or not isinstance(signature, str) or not isinstance(timestamp, str):
        raise DiscordInteractionVerificationError("Invalid Discord signature input.")
    try:
        request_time = int(timestamp)
        current_time = time.time() if now is None else now
        if abs(current_time - request_time) > 300:
            raise DiscordInteractionVerificationError("Discord interaction timestamp expired.")
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
        public_key.verify(bytes.fromhex(signature), timestamp.encode("ascii") + body)
    except (ValueError, TypeError, InvalidSignature, UnicodeError) as exc:
        raise DiscordInteractionVerificationError("Invalid Discord interaction signature.") from exc
    return True
