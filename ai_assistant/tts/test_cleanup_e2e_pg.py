"""Isolated PostgreSQL and fake-object-storage cleanup tests."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.db import connection
from django.test import TransactionTestCase

from .audio_cleanup import AudioCleanupWorker
from .audio_cleanup_pg import PostgresAudioRepository, StorageLimits


class FakeAudioStore:
    def __init__(self):
        self.objects = {}
        self.deletions = []
        self.fail_next_delete = False

    def save(self, *, request_id, audio):
        self.objects.setdefault(request_id, audio)

    def load(self, *, request_id):
        return self.objects.get(request_id)

    def delete(self, *, request_id):
        self.deletions.append(request_id)
        if self.fail_next_delete:
            self.fail_next_delete = False
            raise OSError("simulated R2 failure")
        self.objects.pop(request_id, None)


class CleanupEndToEndPostgresTests(TransactionTestCase):
    def setUp(self):
        if connection.vendor != "postgresql":
            raise RuntimeError("PostgreSQL required")

        # TransactionTestCase does not flush these raw SQL tables.
        # Reset only the isolated test database before each test.
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM tts_audio_cleanup")
            cursor.execute("DELETE FROM tts_audio_budget")


        limits = StorageLimits(
            max_bytes=1024,
            max_objects=3,
            max_uploads_per_day=10,
        )
        self.repo = PostgresAudioRepository(
            global_limits=limits,
            account_limits=limits,
        )
        self.store = FakeAudioStore()
        self.worker = AudioCleanupWorker(
            repository=self.repo,
            audio_store=self.store,
        )
        self.request_id = uuid4()
        self.expiry = datetime.now(timezone.utc) + timedelta(
            minutes=15
        )

    def reserve(self):
        return self.repo.reserve(
            request_id=self.request_id,
            account_id=1,
            size_bytes=4,
            expires_at=self.expiry,
        )

    def reserve_and_store(self):
        self.assertTrue(self.reserve())
        self.store.save(
            request_id=self.request_id,
            audio=b"data",
        )

    def budget(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT bytes_reserved, objects_reserved, "
                "uploads_today FROM tts_audio_budget "
                "WHERE scope='global'"
            )
            return cursor.fetchone()

    def queued(self):
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM tts_audio_cleanup"
            )
            return cursor.fetchone()[0]

    def test_reservation_precedes_external_write(self):
        self.assertTrue(self.reserve())
        self.assertEqual(self.queued(), 1)
        self.assertEqual(self.budget(), (4, 1, 1))
        self.assertIsNone(
            self.store.load(request_id=self.request_id)
        )

    def test_not_deleted_before_expiry(self):
        self.reserve_and_store()
        result = self.worker.run_once(
            now=self.expiry - timedelta(seconds=1),
            limit=10,
        )
        self.assertEqual(result["deleted"], 0)
        self.assertEqual(self.store.deletions, [])
        self.assertEqual(self.queued(), 1)
        self.assertEqual(self.budget(), (4, 1, 1))

    def test_expired_audio_deleted_and_quota_released(self):
        self.reserve_and_store()
        result = self.worker.run_once(
            now=self.expiry + timedelta(seconds=1),
            limit=10,
        )
        self.assertEqual(result["deleted"], 1)
        self.assertIsNone(
            self.store.load(request_id=self.request_id)
        )
        self.assertEqual(self.queued(), 0)
        self.assertEqual(self.budget(), (0, 0, 1))

    def test_failed_delete_retried_and_recovers(self):
        self.reserve_and_store()
        self.store.fail_next_delete = True
        due = self.expiry + timedelta(seconds=1)

        first = self.worker.run_once(now=due, limit=10)
        self.assertEqual(first["deleted"], 0)
        self.assertEqual(first["retried"], 1)
        self.assertEqual(self.queued(), 1)
        self.assertEqual(self.budget(), (4, 1, 1))

        second = self.worker.run_once(
            now=due + timedelta(minutes=6),
            limit=10,
        )
        self.assertEqual(second["deleted"], 1)
        self.assertEqual(self.queued(), 0)
        self.assertEqual(self.budget(), (0, 0, 1))

    def test_aborted_upload_reservation_cleaned(self):
        self.assertTrue(self.reserve())
        result = self.worker.run_once(
            now=self.expiry + timedelta(seconds=1),
            limit=10,
        )
        self.assertEqual(result["deleted"], 1)
        self.assertEqual(self.queued(), 0)
        self.assertEqual(self.budget(), (0, 0, 1))
