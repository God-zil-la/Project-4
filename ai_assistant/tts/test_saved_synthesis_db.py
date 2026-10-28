"""Database integration tests for saved-response TTS."""
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from . import authorization, saved_service, saved_synthesis
from .models import TTSRequest


class SavedSynthesisDatabaseTests(TransactionTestCase):
    def test_full_dispatch_and_replay_use_one_database_request(self):
        user = get_user_model().objects.create_user(username='saved-synthesis-db-owner')
        args = {
            'user': user,
            'assistant_id': 7,
            'conversation_id': uuid4(),
            'message_id': 42,
            'request_id': uuid4(),
        }

        with patch.object(authorization, '_effective_plan', return_value='premium'), \
             patch.object(authorization, '_owns_assistant', return_value=True), \
             patch.object(saved_service, 'get_assistant_message', return_value='Saved answer'), \
             patch.object(saved_synthesis, 'get_assistant_message', return_value='Saved answer'), \
             patch.object(saved_synthesis.MockProvider, 'synthesize', return_value=b'mock-audio') as provider:

            first = saved_synthesis.synthesize_saved_response(**args)
            second = saved_synthesis.synthesize_saved_response(**args)

        self.assertEqual(first.state, 'succeeded')
        self.assertEqual(first.audio, b'mock-audio')
        self.assertEqual(second.state, 'succeeded')
        self.assertIsNone(second.audio)
        self.assertEqual(TTSRequest.objects.count(), 1)
        self.assertEqual(TTSRequest.objects.get().state, 'succeeded')
        provider.assert_called_once_with('Saved answer')

    def test_concurrent_saved_requests_dispatch_provider_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from django.db import close_old_connections

        user = get_user_model().objects.create_user(username='saved-concurrent-owner')
        args = {
            'user': user,
            'assistant_id': 7,
            'conversation_id': uuid4(),
            'message_id': 42,
            'request_id': uuid4(),
        }

        def invoke():
            close_old_connections()
            try:
                return saved_synthesis.synthesize_saved_response(**args)
            finally:
                close_old_connections()

        with patch.object(authorization, '_effective_plan', return_value='premium'), \
             patch.object(authorization, '_owns_assistant', return_value=True), \
             patch.object(saved_service, 'get_assistant_message', return_value='Saved answer'), \
             patch.object(saved_synthesis, 'get_assistant_message', return_value='Saved answer'), \
             patch.object(saved_synthesis.MockProvider, 'synthesize', return_value=b'mock-audio') as provider:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _: invoke(), range(2)))

        self.assertEqual(TTSRequest.objects.count(), 1)
        self.assertEqual(TTSRequest.objects.get().state, 'succeeded')
        self.assertIn(sorted(r.state for r in results), [['dispatched', 'succeeded'], ['succeeded', 'succeeded']])
        self.assertTrue(all(r.state in ('dispatched', 'succeeded') for r in results))
        self.assertEqual(sum(r.audio is not None for r in results), 1)
        provider.assert_called_once_with('Saved answer')
