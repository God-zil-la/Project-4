"""Extra safety contracts for cleanup retries and lost leases."""
from datetime import datetime, timedelta, timezone
from unittest import TestCase
from unittest.mock import Mock
from uuid import uuid4
from .audio_cleanup import AudioCleanupWorker, CleanupJob


class WorkerLeaseSafetyTests(TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 16, tzinfo=timezone.utc)
        self.job = CleanupJob(uuid4(), self.now - timedelta(minutes=1))
        self.repo = Mock()
        self.audio_store = Mock()
        self.repo.claim_due.return_value = [(self.job, uuid4())]
        self.worker = AudioCleanupWorker(repository=self.repo, audio_store=self.audio_store)

    def test_lost_lease_is_not_counted_as_completed(self):
        self.repo.acknowledge.return_value = False
        self.assertEqual(self.worker.run_once(now=self.now)['deleted'], 0)

    def test_successful_ack_counts_as_completed(self):
        self.repo.acknowledge.return_value = True
        self.assertEqual(self.worker.run_once(now=self.now)['deleted'], 1)

    def test_failed_delete_retains_queue_when_retry_loses_lease(self):
        self.audio_store.delete.side_effect = OSError('object store unavailable')
        self.repo.retry.return_value = False
        self.assertEqual(self.worker.run_once(now=self.now)['retried'], 0)
        self.repo.acknowledge.assert_not_called()

    def test_failed_delete_retried_when_lease_owned(self):
        self.audio_store.delete.side_effect = OSError('object store unavailable')
        self.repo.retry.return_value = True
        self.assertEqual(self.worker.run_once(now=self.now)['retried'], 1)
