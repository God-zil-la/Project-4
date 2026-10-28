"""Safety tests for the disabled-by-default cleanup runner."""

from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import Mock, patch

from .cleanup_runner import execute_cleanup


class CleanupRunnerTests(TestCase):
    def setUp(self):
        self.repository = Mock()
        self.store = Mock()
        self.repository.claim_due.return_value = []
        self.now = datetime.now(timezone.utc)

    def test_disabled_by_default(self):
        with self.assertRaises(RuntimeError):
            execute_cleanup(
                repository=self.repository,
                audio_store=self.store,
            )
        self.repository.claim_due.assert_not_called()

    def test_explicit_disable_rejected(self):
        with self.assertRaises(RuntimeError):
            execute_cleanup(
                repository=self.repository,
                audio_store=self.store,
                enabled=False,
            )
        self.repository.claim_due.assert_not_called()

    def test_truthy_string_cannot_enable(self):
        with self.assertRaises(RuntimeError):
            execute_cleanup(
                repository=self.repository,
                audio_store=self.store,
                enabled="true",
            )
        self.repository.claim_due.assert_not_called()

    def test_missing_repository_rejected(self):
        with self.assertRaises(ValueError):
            execute_cleanup(
                repository=None,
                audio_store=self.store,
                enabled=True,
            )

    def test_missing_store_rejected(self):
        with self.assertRaises(ValueError):
            execute_cleanup(
                repository=self.repository,
                audio_store=None,
                enabled=True,
            )

    def test_zero_batch_rejected(self):
        with self.assertRaises(ValueError):
            execute_cleanup(
                repository=self.repository,
                audio_store=self.store,
                enabled=True,
                limit=0,
            )

    def test_oversized_batch_rejected(self):
        with self.assertRaises(ValueError):
            execute_cleanup(
                repository=self.repository,
                audio_store=self.store,
                enabled=True,
                limit=101,
            )

    def test_boolean_batch_rejected(self):
        with self.assertRaises(ValueError):
            execute_cleanup(
                repository=self.repository,
                audio_store=self.store,
                enabled=True,
                limit=True,
            )

    def test_naive_time_rejected(self):
        with self.assertRaises(ValueError):
            execute_cleanup(
                repository=self.repository,
                audio_store=self.store,
                enabled=True,
                now=datetime(2026, 10, 16),
            )

    def test_enabled_empty_queue(self):
        result = execute_cleanup(
            repository=self.repository,
            audio_store=self.store,
            enabled=True,
            now=self.now,
            limit=10,
        )
        self.repository.claim_due.assert_called_once()
        self.store.delete.assert_not_called()
        self.assertIsNotNone(result)

    def test_worker_receives_batch_limit(self):
        execute_cleanup(
            repository=self.repository,
            audio_store=self.store,
            enabled=True,
            now=self.now,
            limit=7,
        )
        kwargs = self.repository.claim_due.call_args.kwargs
        self.assertEqual(kwargs["limit"], 7)
        self.assertEqual(kwargs["now"], self.now)
