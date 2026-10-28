"""Focused tests for saved-response synthesis dispatch safety."""
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from . import saved_synthesis, service
from .errors import Conflict


class SavedSynthesisTests(SimpleTestCase):
    def test_changed_message_after_claim_never_calls_provider(self):
        request_id = uuid4()
        row = type('Row', (), {
            'pk': uuid4(),
            'request_id': request_id,
            'fingerprint': 'original',
        })()

        with patch.object(saved_synthesis, 'prepare_saved_response', return_value=row), \
             patch.object(service, 'claim', return_value=True), \
             patch.object(saved_synthesis, 'get_assistant_message', return_value='Changed'), \
             patch.object(saved_synthesis, 'validate_saved_response',
                          return_value=(request_id, 'changed')), \
             patch.object(service, 'finish') as finish, \
             patch.object(saved_synthesis.MockProvider, 'synthesize') as provider:
            with self.assertRaises(Conflict):
                saved_synthesis.synthesize_saved_response(
                    user=type('User', (), {'pk': 12})(),
                    assistant_id=7,
                    conversation_id=uuid4(),
                    message_id=42,
                    request_id=request_id,
                )

        finish.assert_called_once_with(
            user_id=12, row_id=row.pk, state='not_processed',
        )
        provider.assert_not_called()

    def test_repeated_request_does_not_call_provider(self):
        request_id = uuid4()
        row = type('Row', (), {
            'pk': uuid4(),
            'request_id': request_id,
            'state': 'succeeded',
            'refresh_from_db': lambda self: None,
        })()

        with patch.object(saved_synthesis, 'prepare_saved_response', return_value=row), \
             patch.object(service, 'claim', return_value=False) as claim, \
             patch.object(saved_synthesis, 'get_assistant_message') as lookup, \
             patch.object(saved_synthesis.MockProvider, 'synthesize') as provider:
            result = saved_synthesis.synthesize_saved_response(
                user=type('User', (), {'pk': 12})(),
                assistant_id=7,
                conversation_id=uuid4(),
                message_id=42,
                request_id=request_id,
            )

        self.assertEqual(result.state, 'succeeded')
        self.assertIsNone(result.audio)
        claim.assert_called_once()
        lookup.assert_not_called()
        provider.assert_not_called()

    def test_revoked_access_after_synthesis_withholds_audio(self):
        from .errors import AuthorizationDenied

        request_id = uuid4()
        row = type('Row', (), {
            'pk': uuid4(),
            'request_id': request_id,
            'fingerprint': 'original',
        })()

        with patch.object(saved_synthesis, 'prepare_saved_response', return_value=row), \
             patch.object(service, 'claim', return_value=True), \
             patch.object(saved_synthesis, 'get_assistant_message',
                          side_effect=['Saved response', AuthorizationDenied('tts_denied')]), \
             patch.object(saved_synthesis, 'validate_saved_response',
                          return_value=(request_id, 'original')), \
             patch.object(saved_synthesis.MockProvider, 'synthesize',
                          return_value=b'mock-audio') as provider, \
             patch.object(service, 'finish') as finish:

            with self.assertRaises(AuthorizationDenied):
                saved_synthesis.synthesize_saved_response(
                    user=type('User', (), {'pk': 12})(),
                    assistant_id=7,
                    conversation_id=uuid4(),
                    message_id=42,
                    request_id=request_id,
                )

        provider.assert_called_once()
        finish.assert_called_once_with(
            user_id=12, row_id=row.pk, state='succeeded',
        )

    def test_provider_timeout_is_uncertain_without_retry(self):
        request_id = uuid4()
        row = type('Row', (), {
            'pk': uuid4(),
            'request_id': request_id,
            'fingerprint': 'original',
        })()

        with patch.object(saved_synthesis, 'prepare_saved_response', return_value=row), \
             patch.object(service, 'claim', return_value=True), \
             patch.object(saved_synthesis, 'get_assistant_message', return_value='Saved response'), \
             patch.object(saved_synthesis, 'validate_saved_response', return_value=(request_id, 'original')), \
             patch.object(saved_synthesis.MockProvider, 'synthesize', side_effect=TimeoutError('timeout')) as provider, \
             patch.object(service, 'finish') as finish:
            result = saved_synthesis.synthesize_saved_response(
                user=type('User', (), {'pk': 12})(),
                assistant_id=7,
                conversation_id=uuid4(),
                message_id=42,
                request_id=request_id,
            )

        self.assertEqual(result.state, 'uncertain')
        self.assertIsNone(result.audio)
        provider.assert_called_once()
        finish.assert_called_once_with(
            user_id=12, row_id=row.pk, state='uncertain',
        )

    def test_provider_not_processed_records_correct_state(self):
        request_id = uuid4()
        row = type('Row', (), {
            'pk': uuid4(),
            'request_id': request_id,
            'fingerprint': 'original',
        })()

        from .errors import NotProcessed

        with patch.object(saved_synthesis, 'prepare_saved_response', return_value=row), \
             patch.object(service, 'claim', return_value=True), \
             patch.object(saved_synthesis, 'get_assistant_message', return_value='Saved response'), \
             patch.object(saved_synthesis, 'validate_saved_response', return_value=(request_id, 'original')), \
             patch.object(saved_synthesis.MockProvider, 'synthesize', side_effect=NotProcessed('not_processed')) as provider, \
             patch.object(service, 'finish') as finish:
            result = saved_synthesis.synthesize_saved_response(
                user=type('User', (), {'pk': 12})(),
                assistant_id=7,
                conversation_id=uuid4(),
                message_id=42,
                request_id=request_id,
            )

        self.assertEqual(result.state, 'not_processed')
        self.assertIsNone(result.audio)
        provider.assert_called_once()
        finish.assert_called_once_with(
            user_id=12, row_id=row.pk, state='not_processed',
        )
