"""Storage integration regressions using real request rows and mock audio only."""
from contextlib import ExitStack
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone

from . import authorization, saved_service, saved_synthesis, service
from .audio_retrieval import retrieve_audio
from .audio_store_memory import MemoryAudioStore
from .errors import AuthorizationDenied, Conflict
from .models import TTSRequest


class StorageIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='storage-owner')
        self.args = dict(user=self.user, assistant_id=7, conversation_id=uuid4(),
                         message_id=42, request_id=uuid4())
        self.store = MemoryAudioStore()
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for module, name, value in [
            (authorization, '_effective_plan', 'premium'),
            (authorization, '_owns_assistant', True),
            (saved_service, 'get_assistant_message', 'Saved answer'),
            (saved_synthesis, 'get_assistant_message', 'Saved answer'),
        ]:
            self.stack.enter_context(patch.object(module, name, return_value=value))
        self.provider = self.stack.enter_context(patch.object(
            saved_synthesis.MockProvider, 'synthesize', return_value=b'mock-audio'))

    def synthesize(self, **changes):
        return saved_synthesis.synthesize_saved_response(
            **(self.args | changes), audio_store=self.store)

    def retrieve(self, **changes):
        args = {k: self.args[k] for k in ('user', 'assistant_id', 'request_id')}
        return retrieve_audio(**(args | changes), store=self.store)

    def recover(self):
        return saved_synthesis.recover_saved_response(**self.args, audio_store=self.store)

    def test_shared_client_key_cannot_mix_users_audio(self):
        self.synthesize()
        other = get_user_model().objects.create_user(username='other-storage-owner')
        self.provider.return_value = b'other-audio'
        self.synthesize(user=other)
        self.assertEqual(self.retrieve(), b'mock-audio')
        self.assertEqual(self.retrieve(user=other), b'other-audio')
        self.assertEqual(TTSRequest.objects.count(), 2)
        self.assertIsNone(self.synthesize().audio)
        self.assertEqual(self.provider.call_count, 2)
        stranger = get_user_model().objects.create_user(username='stranger')
        with self.assertRaises(AuthorizationDenied):
            self.retrieve(user=stranger)

    def test_storage_failure_stays_uncertain_without_resynthesis(self):
        with patch.object(self.store, 'save', side_effect=OSError('storage unavailable')):
            with self.assertRaises(OSError):
                self.synthesize()
        self.assertEqual(TTSRequest.objects.get().state, 'uncertain')
        self.assertIsNone(self.retrieve())
        self.assertEqual(self.recover().state, 'uncertain')
        self.assertEqual(self.synthesize().state, 'uncertain')
        self.provider.assert_called_once()

    def test_commit_failure_recovers_retained_bytes_idempotently(self):
        with patch.object(service, 'finish', side_effect=RuntimeError('commit failed')):
            with self.assertRaises(RuntimeError):
                self.synthesize()
        self.assertEqual(TTSRequest.objects.get().state, 'dispatched')
        self.assertIsNone(self.retrieve())
        self.assertEqual(self.recover().audio, b'mock-audio')
        self.assertEqual(self.recover().audio, b'mock-audio')
        self.provider.assert_called_once()

    def test_expired_audio_is_not_regenerated_or_renewed(self):
        self.synthesize()
        with patch('ai_assistant.tts.audio_store_memory.timezone.now',
                   return_value=timezone.now() + timedelta(minutes=16)):
            self.assertIsNone(self.retrieve())
            self.assertIsNone(self.recover().audio)
            self.assertIsNone(self.synthesize().audio)
        self.provider.assert_called_once()

    def test_revoked_access_before_storage_saves_nothing(self):
        with patch.object(saved_synthesis, 'get_assistant_message', side_effect=[
                'Saved answer', AuthorizationDenied('tts_denied')]):
            with self.assertRaises(AuthorizationDenied):
                self.synthesize()
        row = TTSRequest.objects.get()
        self.assertEqual(row.state, 'uncertain')
        self.assertIsNone(self.store.load(request_id=row.pk))

    def test_recovery_denies_revoked_user_and_changed_message(self):
        with patch.object(service, 'finish', side_effect=RuntimeError('commit failed')):
            with self.assertRaises(RuntimeError):
                self.synthesize()
        with patch.object(authorization, '_effective_plan', return_value='free'):
            with self.assertRaises(AuthorizationDenied):
                self.recover()
        with patch.object(saved_service, 'get_assistant_message', return_value='Changed'):
            with self.assertRaises(Conflict):
                self.recover()
        self.assertEqual(TTSRequest.objects.get().state, 'dispatched')
        self.provider.assert_called_once()
