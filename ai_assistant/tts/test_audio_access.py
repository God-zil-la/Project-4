from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase

from .audio_access import authorize_audio_request
from .errors import AuthorizationDenied


class AudioAccessTests(SimpleTestCase):
    def setUp(self):
        self.user = Mock()
        self.user.pk = 12
        self.request_id = uuid4()

    @patch("ai_assistant.tts.audio_access.TTSRequest.objects.filter")
    @patch("ai_assistant.tts.audio_access.authorize")
    def test_owner_can_access_request(self, authorize, filter_requests):
        authorize.return_value = 12
        row = Mock()
        filter_requests.return_value.first.return_value = row

        result = authorize_audio_request(
            user=self.user,
            assistant_id=5,
            request_id=self.request_id,
        )

        self.assertIs(result, row)
        filter_requests.assert_called_once_with(
            account__user_id=12,
            assistant_id=5,
            request_id=self.request_id,
        )

    @patch("ai_assistant.tts.audio_access.TTSRequest.objects.filter")
    @patch("ai_assistant.tts.audio_access.authorize")
    def test_missing_or_other_users_request_denied(self, authorize, filter_requests):
        authorize.return_value = 12
        filter_requests.return_value.first.return_value = None

        with self.assertRaises(AuthorizationDenied):
            authorize_audio_request(
                user=self.user,
                assistant_id=5,
                request_id=self.request_id,
            )

    @patch("ai_assistant.tts.audio_access.TTSRequest.objects.filter")
    @patch("ai_assistant.tts.audio_access.authorize")
    def test_revoked_access_denied(self, authorize, filter_requests):
        authorize.side_effect = AuthorizationDenied("tts_denied")

        with self.assertRaises(AuthorizationDenied):
            authorize_audio_request(
                user=self.user,
                assistant_id=5,
                request_id=self.request_id,
            )

        filter_requests.assert_not_called()
