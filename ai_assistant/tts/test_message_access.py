"""Isolated security tests for saved assistant message access."""
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase

from .errors import AuthorizationDenied
from .message_access import get_assistant_message


class MessageAccessTests(SimpleTestCase):
    def setUp(self):
        self.user = Mock()
        self.user.pk = 12
        self.conversation_id = uuid4()
        self.kwargs = {
            'user': self.user,
            'assistant_id': 7,
            'conversation_id': self.conversation_id,
            'message_id': 42,
        }

    def test_valid_assistant_message(self):
        message = Mock(message='Saved assistant response')
        model = Mock()
        model.objects.get.return_value = message

        with patch('ai_assistant.tts.message_access.authorize', return_value=12) as auth, \
             patch('ai_assistant.tts.message_access.apps.get_model', return_value=model):
            result = get_assistant_message(**self.kwargs)

        self.assertEqual(result, 'Saved assistant response')
        self.assertEqual(auth.call_count, 2)
        model.objects.get.assert_called_once_with(
            pk=42,
            user_id=12,
            bot_id=7,
            conversation__public_id=self.conversation_id,
            conversation__user_id=12,
            conversation__bot_id=7,
            sender='assistant',
        )

    def test_invalid_message_ids_denied(self):
        for value in (None, 0, -1, '42', True):
            with self.subTest(value=value):
                with patch('ai_assistant.tts.message_access.authorize', return_value=12), \
                     patch('ai_assistant.tts.message_access.apps.get_model') as lookup:
                    with self.assertRaises(AuthorizationDenied):
                        get_assistant_message(**(self.kwargs | {'message_id': value}))
                    lookup.assert_not_called()

    def test_invalid_conversation_id_denied(self):
        with patch('ai_assistant.tts.message_access.authorize', return_value=12), \
             patch('ai_assistant.tts.message_access.apps.get_model') as lookup:
            with self.assertRaises(AuthorizationDenied):
                get_assistant_message(**(self.kwargs | {'conversation_id': 'invalid'}))
            lookup.assert_not_called()

    def test_missing_or_inaccessible_message_denied(self):
        model = Mock()
        model.objects.get.side_effect = LookupError('not accessible')
        with patch('ai_assistant.tts.message_access.authorize', return_value=12), \
             patch('ai_assistant.tts.message_access.apps.get_model', return_value=model):
            with self.assertRaises(AuthorizationDenied):
                get_assistant_message(**self.kwargs)

    def test_revoked_access_before_lookup_denied(self):
        with patch('ai_assistant.tts.message_access.authorize', side_effect=AuthorizationDenied('tts_denied')), \
             patch('ai_assistant.tts.message_access.apps.get_model') as lookup:
            with self.assertRaises(AuthorizationDenied):
                get_assistant_message(**self.kwargs)
            lookup.assert_not_called()

    def test_revoked_access_after_lookup_denied(self):
        model = Mock()
        model.objects.get.return_value = Mock(message='Private content')
        with patch('ai_assistant.tts.message_access.authorize',
                   side_effect=[12, AuthorizationDenied('tts_denied')]), \
             patch('ai_assistant.tts.message_access.apps.get_model', return_value=model):
            with self.assertRaises(AuthorizationDenied):
                get_assistant_message(**self.kwargs)
