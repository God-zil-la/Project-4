"""Isolated contract tests; no R2 credentials or external HTTP."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase

from .audio_storage import AUDIO_TTL
from .durable_r2_audio_store import DurableR2AudioStore


class DurableR2AudioStoreTests(SimpleTestCase):
    def setUp(self):
        self.id = uuid4()
        self.created = datetime.now(timezone.utc) - timedelta(minutes=1)
        self.row = SimpleNamespace(
            pk=self.id, account_id=41, created_at=self.created,
            state='dispatched',
        )
        self.repo, self.r2 = Mock(), Mock()
        self.store = DurableR2AudioStore(
            repository=self.repo, r2_store=self.r2, user_id=12,
        )

    def _lookup(self):
        return patch.object(self.store, '_request', return_value=self.row)

    def test_reserve_precedes_external_write(self):
        events = []
        self.repo.reserve.side_effect = lambda **kw: events.append('reserve')
        self.r2.save.side_effect = lambda **kw: events.append('r2')
        with self._lookup():
            self.store.save(request_id=self.id, audio=b'abc')
        self.assertEqual(events, ['reserve', 'r2'])
        self.assertEqual(self.repo.reserve.call_args.kwargs['account_id'], 41)
        self.assertEqual(self.repo.reserve.call_args.kwargs['expires_at'], self.created + AUDIO_TTL)
        self.assertEqual(self.r2.save.call_args.kwargs['expires_at'], self.created + AUDIO_TTL)

    def test_reservation_failure_blocks_r2(self):
        self.repo.reserve.side_effect = RuntimeError('db down')
        with self._lookup(), self.assertRaisesRegex(RuntimeError, 'db down'):
            self.store.save(request_id=self.id, audio=b'abc')
        self.r2.save.assert_not_called()

    def test_r2_failure_retains_cleanup_reservation(self):
        self.r2.save.side_effect = RuntimeError('network lost')
        with self._lookup(), self.assertRaisesRegex(RuntimeError, 'network lost'):
            self.store.save(request_id=self.id, audio=b'abc')
        self.repo.reserve.assert_called_once()

    def test_expired_request_cannot_be_reuploaded(self):
        self.row.created_at = datetime.now(timezone.utc) - timedelta(minutes=16)
        with self._lookup(), self.assertRaisesRegex(ValueError, 'expired'):
            self.store.save(request_id=self.id, audio=b'abc')
        self.repo.reserve.assert_not_called()
        self.r2.save.assert_not_called()

    def test_unstarted_request_rejected(self):
        self.row.state = 'pending'
        with self._lookup(), self.assertRaisesRegex(ValueError, 'not_dispatched'):
            self.store.save(request_id=self.id, audio=b'abc')
        self.repo.reserve.assert_not_called()

    def test_expired_audio_cannot_be_read(self):
        self.row.created_at = datetime.now(timezone.utc) - timedelta(minutes=16)
        with self._lookup():
            self.assertIsNone(self.store.load(request_id=self.id))
        self.r2.load.assert_not_called()

    def test_exact_retry_uses_original_expiry(self):
        self.repo.reserve.return_value = False
        with self._lookup():
            self.store.save(request_id=self.id, audio=b'abc')
            self.store.save(request_id=self.id, audio=b'abc')
        deadlines = [call.kwargs['expires_at'] for call in self.r2.save.call_args_list]
        self.assertEqual(deadlines, [self.created + AUDIO_TTL] * 2)
