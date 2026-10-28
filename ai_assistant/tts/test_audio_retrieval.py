from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase

from .audio_retrieval import retrieve_audio
from .errors import AuthorizationDenied


class AudioRetrievalTests(SimpleTestCase):
    def setUp(self):
        self.user = Mock()
        self.key = uuid4()
        self.store = Mock()
        self.store.load.return_value = b"test-audio"
        self.row = Mock(pk=uuid4(), state="succeeded")
        self.args = dict(
            user=self.user,
            assistant_id=5,
            request_id=self.key,
            store=self.store,
        )

    @patch("ai_assistant.tts.audio_retrieval.authorize_audio_request")
    def test_successful_retrieval(self, authorize):
        authorize.return_value = self.row
        self.assertEqual(retrieve_audio(**self.args), b"test-audio")
        self.assertEqual(authorize.call_count, 2)

    @patch("ai_assistant.tts.audio_retrieval.authorize_audio_request")
    def test_unfinished_request_returns_no_audio(self, authorize):
        authorize.return_value = Mock(state="dispatched")
        self.assertIsNone(retrieve_audio(**self.args))
        self.store.load.assert_not_called()

    @patch("ai_assistant.tts.audio_retrieval.authorize_audio_request")
    def test_missing_or_expired_audio(self, authorize):
        authorize.return_value = self.row
        self.store.load.return_value = None
        self.assertIsNone(retrieve_audio(**self.args))

    @patch("ai_assistant.tts.audio_retrieval.authorize_audio_request")
    def test_revocation_after_storage_read(self, authorize):
        authorize.side_effect = [
            self.row,
            AuthorizationDenied("tts_denied"),
        ]
        with self.assertRaises(AuthorizationDenied):
            retrieve_audio(**self.args)

    @patch("ai_assistant.tts.audio_retrieval.authorize_audio_request")
    def test_changed_request_state_returns_no_audio(self, authorize):
        authorize.side_effect = [
            self.row,
            Mock(pk=self.row.pk, state="uncertain"),
        ]
        self.assertIsNone(retrieve_audio(**self.args))

    @patch("ai_assistant.tts.audio_retrieval.authorize_audio_request")
    def test_different_request_on_recheck_returns_no_audio(self, authorize):
        authorize.side_effect = [
            self.row,
            Mock(pk=uuid4(), state="succeeded"),
        ]
        self.assertIsNone(retrieve_audio(**self.args))
