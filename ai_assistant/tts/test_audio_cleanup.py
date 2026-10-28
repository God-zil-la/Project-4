import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from ai_assistant.tts.audio_cleanup import (
    AudioCleanupWorker, CleanupJob
)


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 16, tzinfo=timezone.utc)
        self.repository = MagicMock()
        self.audio_store = MagicMock()
        self.worker = AudioCleanupWorker(
            repository=self.repository,
            audio_store=self.audio_store,
        )
        self.job = CleanupJob(
            request_id=uuid4(),
            expires_at=self.now - timedelta(minutes=1),
        )

    def test_expired_audio_deleted(self):
        self.repository.claim_due.return_value = [(self.job, "lease1")]
        result = self.worker.run_once(now=self.now)
        self.assertEqual(result["deleted"], 1)
        self.audio_store.delete.assert_called_once_with(
            request_id=self.job.request_id
        )
        self.repository.acknowledge.assert_called_once()

    def test_failed_deletion_retried(self):
        self.repository.claim_due.return_value = [(self.job, "lease1")]
        self.audio_store.delete.side_effect = IOError("simulated")
        result = self.worker.run_once(now=self.now)
        self.assertEqual(result["retried"], 1)
        self.repository.acknowledge.assert_not_called()
        self.repository.retry.assert_called_once()

    def test_future_audio_not_deleted(self):
        future = CleanupJob(
            request_id=uuid4(),
            expires_at=self.now + timedelta(minutes=3),
        )
        self.repository.claim_due.return_value = [(future, "lease2")]
        self.worker.run_once(now=self.now)
        self.audio_store.delete.assert_not_called()
        self.repository.retry.assert_called_once()

    def test_empty_queue(self):
        self.repository.claim_due.return_value = []
        self.assertEqual(
            self.worker.run_once(now=self.now),
            {"deleted": 0, "retried": 0}
        )

    def test_invalid_batch_size(self):
        with self.assertRaises(ValueError):
            self.worker.run_once(now=self.now, limit=0)

    def test_naive_expiry_rejected(self):
        with self.assertRaises(ValueError):
            CleanupJob(
                request_id=uuid4(),
                expires_at=datetime(2026, 10, 16)
            )

    def test_claim_uses_lease(self):
        self.repository.claim_due.return_value = []
        self.worker.run_once(now=self.now, limit=5)
        arguments = self.repository.claim_due.call_args.kwargs
        self.assertEqual(arguments["limit"], 5)
        self.assertGreater(arguments["lease_duration"].total_seconds(), 0)


if __name__ == "__main__":
    unittest.main()
