"""Isolated TTS cleanup engine.

The repository must implement durable, atomic leasing for
multiple workers before this can be used in production.
No scheduler or production storage is connected here.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol
from uuid import UUID


LEASE_DURATION = timedelta(minutes=2)
MAX_BATCH = 100


@dataclass(frozen=True)
class CleanupJob:
    request_id: UUID
    expires_at: datetime

    def __post_init__(self):
        if not isinstance(self.request_id, UUID):
            raise ValueError("invalid_request_id")
        if self.expires_at.tzinfo is None:
            raise ValueError("timezone_required")


class CleanupRepository(Protocol):
    def claim_due(self, *, now, limit, lease_duration):
        """Atomically lease due jobs across all workers."""

    def acknowledge(self, *, job, lease):
        """Acknowledge only when this worker still owns the lease."""

    def retry(self, *, job, lease, retry_at):
        """Release owned lease and schedule durable retry."""


class AudioCleanupWorker:
    def __init__(self, *, repository, audio_store):
        self.repository = repository
        self.audio_store = audio_store

    def run_once(self, *, now=None, limit=MAX_BATCH):
        if now is None:
            now = datetime.now(timezone.utc)

        if now.tzinfo is None:
            raise ValueError("timezone_required")
        if not isinstance(limit, int) or not 1 <= limit <= MAX_BATCH:
            raise ValueError("invalid_batch_limit")

        claimed = self.repository.claim_due(
            now=now,
            limit=limit,
            lease_duration=LEASE_DURATION,
        )

        result = {"deleted": 0, "retried": 0}

        for job, lease in claimed:
            if job.expires_at > now:
                if self.repository.retry(
                    job=job,
                    lease=lease,
                    retry_at=job.expires_at,
                ):
                    result["retried"] += 1
                continue

            try:
                self.audio_store.delete(request_id=job.request_id)
            except Exception:
                # Never acknowledge uncertain deletion.
                if self.repository.retry(
                    job=job,
                    lease=lease,
                    retry_at=now + timedelta(minutes=5),
                ):
                    result["retried"] += 1
            else:
                if self.repository.acknowledge(job=job, lease=lease):
                    result["deleted"] += 1

        return result
