"""Opt-in cleanup batch entrypoint; intentionally no scheduler or credentials.

A future deployment can invoke run_cleanup_batch from a reviewed and explicitly
configured scheduler, supplying raw R2AudioStore (not user-scoped wrapper).
"""
from .audio_cleanup import AudioCleanupWorker


def run_cleanup_batch(*, repository, raw_r2_store, now=None, limit=100):
    if repository is None or raw_r2_store is None:
        raise ValueError('cleanup_dependencies_required')
    return AudioCleanupWorker(
        repository=repository, audio_store=raw_r2_store,
    ).run_once(now=now, limit=limit)
