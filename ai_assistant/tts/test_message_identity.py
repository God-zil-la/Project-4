"""Security tests for saved-response TTS identity."""
from uuid import uuid4

from django.test import SimpleTestCase

from .errors import InvalidInput
from .message_identity import validate_saved_response


class SavedResponseIdentityTests(SimpleTestCase):
    def setUp(self):
        self.args = {
            'text': 'Hej världen',
            'assistant_id': 7,
            'conversation_id': uuid4(),
            'message_id': 42,
            'request_id': uuid4(),
        }

    def test_identical_input_has_identical_fingerprint(self):
        self.assertEqual(
            validate_saved_response(**self.args),
            validate_saved_response(**self.args),
        )

    def test_different_message_same_text_changes_fingerprint(self):
        original = validate_saved_response(**self.args)[1]
        changed = validate_saved_response(
            **(self.args | {'message_id': 43})
        )[1]
        self.assertNotEqual(original, changed)

    def test_different_conversation_changes_fingerprint(self):
        original = validate_saved_response(**self.args)[1]
        changed = validate_saved_response(
            **(self.args | {'conversation_id': uuid4()})
        )[1]
        self.assertNotEqual(original, changed)

    def test_changed_text_or_assistant_changes_fingerprint(self):
        original = validate_saved_response(**self.args)[1]
        for changes in ({'text': 'Annat svar'}, {'assistant_id': 8}):
            with self.subTest(changes=changes):
                changed = validate_saved_response(
                    **(self.args | changes)
                )[1]
                self.assertNotEqual(original, changed)

    def test_invalid_message_ids_rejected(self):
        for value in (None, 0, -1, '42', True):
            with self.subTest(value=value):
                with self.assertRaises(InvalidInput):
                    validate_saved_response(
                        **(self.args | {'message_id': value})
                    )

    def test_invalid_conversation_ids_rejected(self):
        for value in (None, '', 'invalid', 123, True):
            with self.subTest(value=value):
                with self.assertRaises(InvalidInput):
                    validate_saved_response(
                        **(self.args | {'conversation_id': value})
                    )
