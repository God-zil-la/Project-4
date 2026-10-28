"""Opt-in R2 S3 client factory. No connections or credentials on import.

Caller must explicitly configure the private R2 bucket and enable storage.
Constructing a boto3 client does not perform a network request; methods do.
"""
import re

from django.conf import settings


_R2_ENDPOINT = re.compile(r"https://[a-f0-9]{32}\.r2\.cloudflarestorage\.com\Z", re.I)


def build_r2_client():
    if getattr(settings, "U62_R2_ENABLED", False) is not True:
        raise RuntimeError("r2_disabled")
    endpoint = getattr(settings, "U62_R2_ENDPOINT_URL", None)
    key_id = getattr(settings, "U62_R2_ACCESS_KEY_ID", None)
    secret = getattr(settings, "U62_R2_SECRET_ACCESS_KEY", None)
    if not isinstance(endpoint, str) or not _R2_ENDPOINT.fullmatch(endpoint):
        raise ValueError("invalid_r2_endpoint")
    if not isinstance(key_id, str) or not key_id.strip():
        raise ValueError("missing_r2_access_key")
    if not isinstance(secret, str) or not secret.strip():
        raise ValueError("missing_r2_secret_key")

    # Lazy imports ensure no client or network access at import time.
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="auto",
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        config=Config(
            connect_timeout=5,
            read_timeout=15,
            retries={"mode": "standard", "max_attempts": 2},
            s3={"addressing_style": "path"},
        ),
    )
