
"""PostgreSQL lease takeover tests; isolated test DB and fake store only."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.db import connection
from django.test import TransactionTestCase

from .audio_cleanup import AudioCleanupWorker, LEASE_DURATION
from .audio_cleanup_pg import PostgresAudioRepository, StorageLimits


class FakeStore:
    def __init__(self):
        self.objects = set()
        self.deleted = []

    def delete(self, *, request_id):
        self.deleted.append(request_id)
        self.objects.discard(request_id)


class CleanupRestartPostgresTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            raise RuntimeError("isolated_postgresql_required")

        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM tts_audio_cleanup")
            cursor.execute("DELETE FROM tts_audio_budget")

        self.limits = StorageLimits(
            max_bytes=1024,
            max_objects=3,
            max_uploads_per_day=10,
        )
        self.request_id = uuid4()
        self.expiry = datetime.now(timezone.utc) + timedelta(minutes=15)
        self.store = FakeStore()
        self.store.objects.add(self.request_id)

        self.assertTrue(
            self.repository().reserve(
                request_id=self.request_id,
                account_id=1,
                size_bytes=4,
                expires_at=self.expiry,
            )
        )

        self.due = self.expiry + timedelta(seconds=1)

    def repository(self):
        return PostgresAudioRepository(
            global_limits=self.limits,
            account_limits=self.limits,
        )

    def budget(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT bytes_reserved, objects_reserved, uploads_today "
                "FROM tts_audio_budget WHERE scope = 'global'"
            )
            return cursor.fetchone()

    def test_unexpired_lease_cannot_be_stolen(self):
        repo = self.repository()
        claimed = repo.claim_due(
            now=self.due,
            limit=1,
            lease_duration=LEASE_DURATION,
        )
        self.assertEqual(len(claimed), 1)

        replacement = AudioCleanupWorker(
            repository=self.repository(),
            audio_store=self.store,
        )

        result = replacement.run_once(
            now=self.due + timedelta(seconds=30),
            limit=1,
        )

        self.assertEqual(result["deleted"], 0)
        self.assertEqual(self.store.deleted, [])
        self.assertEqual(self.budget(), (4, 1, 1))

    def test_expired_lease_recovered_by_new_worker(self):
        repo = self.repository()
        claimed = repo.claim_due(
            now=self.due,
            limit=1,
            lease_duration=LEASE_DURATION,
        )
        self.assertEqual(len(claimed), 1)
        old_job, old_lease = claimed[0]

        # Simulated crash: the original worker never acknowledges.
        replacement = AudioCleanupWorker(
            repository=self.repository(),
            audio_store=self.store,
        )
        recovered_at = self.due + LEASE_DURATION + timedelta(seconds=1)

        result = replacement.run_once(
            now=recovered_at,
            limit=1,
        )

        self.assertEqual(result["deleted"], 1)
        self.assertEqual(self.store.deleted, [self.request_id])
        self.assertNotIn(self.request_id, self.store.objects)
        self.assertFalse(
            repo.acknowledge(job=old_job, lease=old_lease)
        )
        self.assertEqual(self.budget(), (0, 0, 1))

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM tts_audio_cleanup"
            )
            self.assertEqual(cursor.fetchone()[0], 0)
