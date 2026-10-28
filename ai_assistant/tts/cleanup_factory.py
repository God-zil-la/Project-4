"""Explicit dependency factory for TTS cleanup.

No client, database connection or scheduler is created at import.
A separately reviewed client factory must be supplied in settings.
"""

from django.conf import settings
from django.utils.module_loading import import_string

from .audio_cleanup_pg import (
    PostgresAudioRepository,
    StorageLimits,
)
from .r2_audio_store import R2AudioStore


def _positive_limit(name):
    value = getattr(settings, name, None)
    if type(value) is not int or value <= 0:
        raise ValueError(f"invalid_{name.lower()}")
    return value


def _storage_limits(prefix):
    return StorageLimits(
        max_bytes=_positive_limit(prefix + "_MAX_BYTES"),
        max_objects=_positive_limit(prefix + "_MAX_OBJECTS"),
        max_uploads_per_day=_positive_limit(
            prefix + "_MAX_UPLOADS_PER_DAY"
        ),
    )


def build_cleanup_dependencies():
    """Construct dependencies only after explicit enablement."""

    if getattr(settings, "U62_CLEANUP_ENABLED", False) is not True:
        raise RuntimeError("cleanup_disabled")

    if getattr(settings, "U62_R2_ENABLED", False) is not True:
        raise RuntimeError("r2_disabled")

    bucket = getattr(settings, "U62_R2_BUCKET", None)
    if not isinstance(bucket, str) or not bucket.strip():
        raise ValueError("invalid_r2_bucket")

    client_factory_path = getattr(
        settings, "U62_R2_CLIENT_FACTORY", None
    )

    if (
        not isinstance(client_factory_path, str)
        or not client_factory_path.strip()
    ):
        raise ValueError("missing_r2_client_factory")

    global_limits = _storage_limits("U62_GLOBAL_STORAGE")
    account_limits = _storage_limits("U62_ACCOUNT_STORAGE")

    client_factory = import_string(client_factory_path)
    if not callable(client_factory):
        raise ValueError("invalid_r2_client_factory")

    client = client_factory()
    if client is None:
        raise RuntimeError("r2_client_unavailable")

    repository = PostgresAudioRepository(
        global_limits=global_limits,
        account_limits=account_limits,
    )

    store = R2AudioStore(
        client=client,
        bucket=bucket,
    )

    return repository, store
