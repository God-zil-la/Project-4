"""One-way storage for high-entropy customer credentials."""
import hashlib
import re
import secrets

from django.views.decorators.debug import sensitive_variables


@sensitive_variables()
def hash_api_key(secret):
    return "sha256$" + hashlib.sha256(secret.encode("utf-8")).hexdigest()


def unused_api_key_hash():
    # A new account has no retrievable customer credential until it rotates.
    return hash_api_key(secrets.token_hex(32))


def valid_api_key_format(secret):
    return bool(isinstance(secret, str) and re.fullmatch(
        r"(?:api_[0-9a-f]{64}|[0-9a-f]{32}|[0-9a-f]{64})", secret
    ))
