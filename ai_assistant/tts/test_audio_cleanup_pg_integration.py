"""PostgreSQL integration tests; isolated test database only."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from django.db import connection
from django.test import TransactionTestCase

from .audio_cleanup_pg import (
    PostgresAudioRepository,
    StorageLimits,
    StorageQuotaExceeded,
)


class CleanupPostgresTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if connection.vendor != 'postgresql':
            raise RuntimeError('PostgreSQL required')
        # Cleanup schema is created by migration 0002, not test code.
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('tts_audio_cleanup'), to_regclass('tts_audio_budget')")
            if not all(cursor.fetchone() or ()):
                raise RuntimeError('cleanup_migration_missing')

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM tts_audio_cleanup")
            cursor.execute("DELETE FROM tts_audio_budget")

        self.limits = StorageLimits(
            max_bytes=1024,
            max_objects=2,
            max_uploads_per_day=10,
        )
        self.repo = PostgresAudioRepository(
            global_limits=self.limits,
            account_limits=self.limits,
        )
        self.now = datetime.now(timezone.utc)
        self.expiry = self.now + timedelta(minutes=15)

    def reserve(self, request_id=None, account_id=1, size=100):
        request_id = request_id or uuid4()
        result = self.repo.reserve(
            request_id=request_id,
            account_id=account_id,
            size_bytes=size,
            expires_at=self.expiry,
        )
        return request_id, result

    def test_reservation_persists(self):
        request_id, created = self.reserve()
        self.assertTrue(created)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT account_id, size_bytes FROM tts_audio_cleanup "
                "WHERE request_id=%s",
                [str(request_id)],
            )
            self.assertEqual(cursor.fetchone(), (1, 100))

    def test_replay_does_not_charge_twice(self):
        request_id, _ = self.reserve()
        _, created = self.reserve(request_id=request_id)
        self.assertFalse(created)

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT bytes_reserved, objects_reserved, "
                "uploads_today FROM tts_audio_budget "
                "WHERE scope='global'"
            )
            self.assertEqual(cursor.fetchone(), (100, 1, 1))

    def test_global_capacity_rejects_overflow(self):
        self.reserve(size=700)
        with self.assertRaises(StorageQuotaExceeded):
            self.reserve(size=400, account_id=2)

    def test_account_isolation_on_replay(self):
        request_id, _ = self.reserve(account_id=1)
        with self.assertRaises(ValueError):
            self.reserve(request_id=request_id, account_id=2)

    def test_claim_and_ack_release_storage(self):
        request_id, _ = self.reserve()
        jobs = self.repo.claim_due(
            now=self.expiry + timedelta(seconds=1),
            limit=10,
            lease_duration=timedelta(minutes=2),
        )
        self.assertEqual(len(jobs), 1)
        job, lease = jobs[0]
        self.assertEqual(job.request_id, request_id)
        self.assertTrue(
            self.repo.acknowledge(job=job, lease=lease)
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT bytes_reserved, objects_reserved "
                "FROM tts_audio_budget WHERE scope='global'"
            )
            self.assertEqual(cursor.fetchone(), (0, 0))

    def test_retry_and_stale_lease(self):
        self.reserve()
        due = self.expiry + timedelta(seconds=1)
        job, lease = self.repo.claim_due(
            now=due,
            limit=1,
            lease_duration=timedelta(minutes=2),
        )[0]

        self.assertTrue(
            self.repo.retry(
                job=job,
                lease=lease,
                retry_at=due + timedelta(minutes=5),
            )
        )

        self.assertFalse(
            self.repo.acknowledge(job=job, lease=lease)
        )

        self.assertEqual(
            self.repo.claim_due(
                now=due,
                limit=1,
                lease_duration=timedelta(minutes=2),
            ),
            [],
        )


    def test_concurrent_duplicate_reservation(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections

        request_id = uuid4()
        barrier = Barrier(2)

        def worker():
            connections.close_all()
            try:
                barrier.wait(timeout=15)
                return self.repo.reserve(
                    request_id=request_id,
                    account_id=1,
                    size_bytes=100,
                    expires_at=self.expiry,
                )
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            results = [future.result(timeout=30) for future in futures]

        self.assertCountEqual(results, [True, False])

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM tts_audio_cleanup "
                "WHERE request_id=%s",
                [str(request_id)],
            )
            self.assertEqual(cursor.fetchone()[0], 1)

            cursor.execute(
                "SELECT bytes_reserved, objects_reserved, "
                "uploads_today FROM tts_audio_budget "
                "WHERE scope='global'"
            )
            self.assertEqual(cursor.fetchone(), (100, 1, 1))

    def test_concurrent_global_quota(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections

        global_limits = StorageLimits(
            max_bytes=1024,
            max_objects=1,
            max_uploads_per_day=10,
        )
        account_limits = StorageLimits(
            max_bytes=1024,
            max_objects=2,
            max_uploads_per_day=10,
        )
        repository = PostgresAudioRepository(
            global_limits=global_limits,
            account_limits=account_limits,
        )

        barrier = Barrier(2)

        def worker(account_id):
            connections.close_all()
            try:
                barrier.wait(timeout=15)
                try:
                    return repository.reserve(
                        request_id=uuid4(),
                        account_id=account_id,
                        size_bytes=100,
                        expires_at=self.expiry,
                    )
                except StorageQuotaExceeded:
                    return "quota_exceeded"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(worker, account_id)
                for account_id in (1, 2)
            ]
            results = [future.result(timeout=30) for future in futures]

        self.assertCountEqual(results, [True, "quota_exceeded"])

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM tts_audio_cleanup"
            )
            self.assertEqual(cursor.fetchone()[0], 1)

            cursor.execute(
                "SELECT bytes_reserved, objects_reserved "
                "FROM tts_audio_budget WHERE scope='global'"
            )
            self.assertEqual(cursor.fetchone(), (100, 1))
