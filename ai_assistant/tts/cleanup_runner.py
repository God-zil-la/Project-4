"""Controlled, opt-in TTS audio cleanup execution.

This module does not start a scheduler, access R2, or connect to a database.
A caller must supply an already configured repository and audio store.
"""

from datetime import datetime, timezone

from .audio_cleanup import AudioCleanupWorker


MAX_CLEANUP_BATCH = 100


def execute_cleanup(
    *,
    repository,
    audio_store,
    enabled=False,
    now=None,
    limit=100,
):
    if enabled is not True:
        raise RuntimeError(
            "TTS cleanup is disabled. Explicit enablement required."
        )

    if type(limit) is not int or not 1 <= limit <= MAX_CLEANUP_BATCH:
        raise ValueError("Invalid cleanup batch size")

    if repository is None or audio_store is None:
        raise ValueError("Repository and audio store are required")

    if now is None:
        now = datetime.now(timezone.utc)

    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("Cleanup time must be timezone-aware")

    if now.utcoffset() is None:
        raise ValueError("Cleanup time must be timezone-aware")

    worker = AudioCleanupWorker(
        repository=repository,
        audio_store=audio_store,
    )

    return worker.run_once(now=now, limit=limit)
