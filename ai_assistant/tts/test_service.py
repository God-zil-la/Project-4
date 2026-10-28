from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection, connections, close_old_connections, transaction, DatabaseError, IntegrityError
from django.test import TransactionTestCase

from . import authorization, service
from .errors import AuthorizationDenied, Conflict, InvalidInput, NotProcessed, TTSError
from .models import TTSAccount, TTSRequest
from .provider import MockProvider


class ServiceTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='owner')
        self.other = get_user_model().objects.create_user(username='other')
        self.plan = 'premium'
        self.owned = True
        self.plan_patch = patch.object(authorization, '_effective_plan', side_effect=lambda _: self.plan)
        self.owner_patch = patch.object(authorization, '_owns_assistant', side_effect=lambda *_: self.owned)
        self.plan_patch.start()
        self.owner_patch.start()
        self.addCleanup(self.plan_patch.stop)
        self.addCleanup(self.owner_patch.stop)

    def args(self, **changes):
        values = dict(user=self.user, assistant_id=7, text='Hej världen', request_id=uuid4())
        values.update(changes)
        return values

    def parallel(self, function, count=6):
        barrier = Barrier(count)
        def worker(i):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return function(i)
            finally:
                connections.close_all()
        with ThreadPoolExecutor(count) as pool:
            return list(pool.map(worker, range(count)))

    def test_success_returns_mock_bytes_without_persisting_text_or_audio(self):
        result = service.synthesize(**self.args())
        self.assertEqual(result.state, 'succeeded')
        self.assertTrue(result.mock)
        self.assertEqual(result.format, 'mp3')
        self.assertEqual(result.audio, b'U62-MOCK-AUDIO-NOT-REAL-MP3')
        self.assertNotIn('Hej världen', str(list(TTSRequest.objects.values())))
        self.assertEqual({f.name for f in TTSRequest._meta.fields},
            {'id', 'account', 'assistant_id', 'request_id', 'fingerprint', 'state', 'created_at', 'updated_at'})

    def test_replay_has_no_audio_or_second_provider_call(self):
        args = self.args()
        with patch.object(MockProvider, 'synthesize', return_value=b'mock') as provider:
            self.assertEqual(service.synthesize(**args).audio, b'mock')
            self.assertIsNone(service.synthesize(**args).audio)
            provider.assert_called_once()
        self.assertEqual(TTSRequest.objects.count(), 1)

    def test_changed_text_or_assistant_conflicts(self):
        args = self.args()
        service.synthesize(**args)
        for changes in ({'text': 'changed'}, {'assistant_id': 8}):
            with self.assertRaises(Conflict):
                service.synthesize(**(args | changes))

    def test_request_key_is_scoped_to_user(self):
        args = self.args()
        service.synthesize(**args)
        service.synthesize(**(args | {'user': self.other}))
        self.assertEqual(TTSRequest.objects.count(), 2)

    def test_unauthorized_and_invalid_input_never_create_requests_or_call_provider(self):
        with patch.object(MockProvider, 'synthesize') as provider:
            self.plan = 'free'
            with self.assertRaises(AuthorizationDenied):
                service.synthesize(**self.args())
            self.plan = 'premium'
            with self.assertRaises(InvalidInput):
                service.synthesize(**self.args(text='<speak>no</speak>'))
            provider.assert_not_called()
        self.assertEqual(TTSRequest.objects.count(), 0)

    def test_revocation_between_prepare_and_claim(self):
        for attribute, value in (('plan', 'free'), ('owned', False)):
            with self.subTest(attribute=attribute):
                self.plan, self.owned = 'premium', True
                args = self.args()
                row = service.prepare(**args)
                setattr(self, attribute, value)
                with self.assertRaises(AuthorizationDenied):
                    service.claim(user=self.user, assistant_id=7, row_id=row.pk)
                row.refresh_from_db()
                self.assertEqual(row.state, 'pending')

    def test_revocation_after_lock_wait(self):
        original = service.lock_account
        def revoke(user_id):
            account = original(user_id)
            self.plan = 'free'
            return account
        with patch.object(service, 'lock_account', side_effect=revoke), self.assertRaises(AuthorizationDenied):
            service.prepare(**self.args())
        self.assertEqual(TTSAccount.objects.count(), 0)

    def test_revocation_during_provider_records_outcome_but_withholds_audio(self):
        def provider(_):
            self.owned = False
            return b'mock'
        with patch.object(MockProvider, 'synthesize', side_effect=provider), self.assertRaises(AuthorizationDenied):
            service.synthesize(**self.args())
        self.assertEqual(TTSRequest.objects.get().state, 'succeeded')

    def test_replay_rechecks_entitlement(self):
        args = self.args()
        service.synthesize(**args)
        self.plan = 'free'
        with self.assertRaises(AuthorizationDenied):
            service.synthesize(**args)

    def test_other_user_or_assistant_cannot_claim(self):
        row = service.prepare(**self.args())
        for user, assistant in ((self.other, 7), (self.user, 8)):
            with self.assertRaises(TTSRequest.DoesNotExist):
                service.claim(user=user, assistant_id=assistant, row_id=row.pk)

    def test_prepare_rollback(self):
        with patch.object(TTSRequest.objects, 'create', side_effect=DatabaseError('injected')), self.assertRaises(DatabaseError):
            service.synthesize(**self.args())
        self.assertEqual(TTSAccount.objects.count(), 0)
        self.assertEqual(TTSRequest.objects.count(), 0)

    def test_claim_rollback_prevents_provider_call(self):
        args = self.args()
        row = service.prepare(**args)
        original = TTSRequest.save
        def fail(saved, *a, **kw):
            original(saved, *a, **kw)
            raise DatabaseError('after write')
        with patch.object(TTSRequest, 'save', fail), patch.object(MockProvider, 'synthesize') as provider:
            with self.assertRaises(DatabaseError):
                service.synthesize(**args)
            provider.assert_not_called()
        row.refresh_from_db()
        self.assertEqual(row.state, 'pending')

    def test_claim_commit_failure_prevents_provider_call(self):
        args = self.args()
        row = service.prepare(**args)
        original = service.claim
        def fail_claim(**kw):
            with patch.object(connection, 'commit', side_effect=DatabaseError('commit failed')):
                return original(**kw)
        with patch.object(service, 'claim', side_effect=fail_claim), patch.object(MockProvider, 'synthesize') as provider:
            with self.assertRaises(DatabaseError):
                service.synthesize(**args)
            provider.assert_not_called()
        row.refresh_from_db()
        self.assertEqual(row.state, 'pending')

    def test_outer_transaction_denied_before_provider(self):
        with transaction.atomic(), patch.object(MockProvider, 'synthesize') as provider:
            with self.assertRaises(TTSError):
                service.synthesize(**self.args())
            provider.assert_not_called()

    def test_provider_observes_committed_claim(self):
        def provider(_):
            self.assertFalse(connection.in_atomic_block)
            states = self.parallel(lambda _: TTSRequest.objects.get().state, count=1)
            self.assertEqual(states, ['dispatched'])
            return b'mock'
        with patch.object(MockProvider, 'synthesize', side_effect=provider):
            self.assertEqual(service.synthesize(**self.args()).state, 'succeeded')

    def test_timeout_and_invalid_response_are_uncertain_without_retry(self):
        for error in (TimeoutError('timeout'), RuntimeError('provider error'), None, b''):
            args = self.args()
            with patch.object(MockProvider, 'synthesize') as provider:
                if isinstance(error, Exception):
                    provider.side_effect = error
                else:
                    provider.return_value = error
                self.assertEqual(service.synthesize(**args).state, 'uncertain')
                self.assertEqual(service.synthesize(**args).state, 'uncertain')
                provider.assert_called_once()

    def test_confirmed_nonprocessing_is_terminal(self):
        args = self.args()
        with patch.object(MockProvider, 'synthesize', side_effect=NotProcessed('mock rejection')) as provider:
            self.assertEqual(service.synthesize(**args).state, 'not_processed')
            self.assertEqual(service.synthesize(**args).state, 'not_processed')
            provider.assert_called_once()

    def test_crash_after_claim_does_not_redispatch(self):
        args = self.args()
        row = service.prepare(**args)
        service.claim(user=self.user, assistant_id=7, row_id=row.pk)
        with patch.object(MockProvider, 'synthesize') as provider:
            self.assertEqual(service.synthesize(**args).state, 'dispatched')
            provider.assert_not_called()

    def test_finish_failure_keeps_dispatched_without_automatic_retry(self):
        args = self.args()
        with patch.object(service, 'finish', side_effect=DatabaseError('failed outcome save')):
            with self.assertRaises(DatabaseError):
                service.synthesize(**args)
        with patch.object(MockProvider, 'synthesize') as provider:
            self.assertEqual(service.synthesize(**args).state, 'dispatched')
            provider.assert_not_called()

    def test_concurrent_requests_synthesize_once(self):
        args = self.args()
        with patch.object(MockProvider, 'synthesize', return_value=b'mock') as provider:
            results = self.parallel(lambda _: service.synthesize(**args))
            provider.assert_called_once()
        self.assertEqual(TTSRequest.objects.count(), 1)
        self.assertEqual(sum(r.audio is not None for r in results), 1)
        self.assertEqual(TTSRequest.objects.get().state, 'succeeded')

    def test_concurrent_changed_payload_accepts_only_one_identity(self):
        args = self.args()
        def attempt(i):
            try:
                return service.prepare(**(args | {'text': str(i)})).pk
            except Conflict:
                return None
        self.assertEqual(sum(r is not None for r in self.parallel(attempt)), 1)

    def test_concurrent_conflicting_outcomes_never_overwrite_terminal_state(self):
        row = service.prepare(**self.args())
        service.claim(user=self.user, assistant_id=7, row_id=row.pk)
        def attempt(i):
            try:
                service.finish(user_id=self.user.pk, row_id=row.pk,
                               state='succeeded' if i % 2 else 'not_processed')
                return True
            except Conflict:
                return False
        self.assertEqual(self.parallel(attempt).count(True), 3)

    def test_constraints(self):
        row = service.prepare(**self.args())
        for update in ({'state': 'invalid'}, {'assistant_id': 0}):
            with self.assertRaises(IntegrityError), transaction.atomic():
                TTSRequest.objects.filter(pk=row.pk).update(**update)
        with self.assertRaises(IntegrityError), transaction.atomic():
            TTSRequest.objects.create(account=row.account, assistant_id=7,
                request_id=row.request_id, fingerprint=row.fingerprint)
