"""U6.3 HTTP audio delivery security tests."""

from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase

from .audio_api import voice_turn_audio
from .models import VoiceTurn
from .service import VoiceAccessDenied


class U63AudioHTTPTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.session_id = uuid4()
        self.request_id = uuid4()

    def request(self, user):
        request = self.factory.get(
            f"/voice/{self.session_id}/{self.request_id}/audio/"
        )
        request.user = user
        return request

    def test_anonymous_user_is_rejected(self):
        response = voice_turn_audio(
            self.request(AnonymousUser()),
            self.session_id,
            self.request_id,
        )

        self.assertEqual(response.status_code, 401)

    @patch("ai_assistant.voice.audio_api._session")
    def test_inaccessible_session_returns_404(self, mock_session):
        mock_session.side_effect = VoiceAccessDenied(
            "access_denied"
        )

        user = Mock()
        user.is_authenticated = True

        response = voice_turn_audio(
            self.request(user),
            self.session_id,
            self.request_id,
        )

        self.assertEqual(response.status_code, 404)

    @patch("ai_assistant.voice.audio_api.VoiceTurn.objects.filter")
    @patch("ai_assistant.voice.audio_api._session")
    def test_missing_turn_returns_404(
        self,
        mock_session,
        mock_filter,
    ):
        user = Mock()
        user.is_authenticated = True

        mock_session.return_value = Mock()
        mock_filter.return_value.first.return_value = None

        response = voice_turn_audio(
            self.request(user),
            self.session_id,
            self.request_id,
        )

        self.assertEqual(response.status_code, 404)

    @patch("ai_assistant.voice.audio_api.retrieve_voice_audio")
    @patch("ai_assistant.voice.audio_api.VoiceTurn.objects.filter")
    @patch("ai_assistant.voice.audio_api._session")
    def test_unfinished_turn_cannot_deliver_audio(
        self,
        mock_session,
        mock_filter,
        mock_retrieve,
    ):
        user = Mock()
        user.is_authenticated = True

        mock_session.return_value = Mock()

        turn = Mock()
        turn.state = VoiceTurn.State.SYNTHESIZING
        turn.assistant_message_id = 10

        mock_filter.return_value.first.return_value = turn

        response = voice_turn_audio(
            self.request(user),
            self.session_id,
            self.request_id,
        )

        self.assertEqual(response.status_code, 409)
        mock_retrieve.assert_not_called()

    @patch("ai_assistant.voice.audio_api.retrieve_voice_audio")
    @patch("ai_assistant.voice.audio_api.VoiceTurn.objects.filter")
    @patch("ai_assistant.voice.audio_api._session")
    def test_completed_turn_delivers_private_mp3(
        self,
        mock_session,
        mock_filter,
        mock_retrieve,
    ):
        user = Mock()
        user.is_authenticated = True

        session = Mock()
        session.assistant_id = 1
        mock_session.return_value = session

        turn = Mock()
        turn.state = VoiceTurn.State.COMPLETED
        turn.assistant_message_id = 10
        turn.request_id = self.request_id

        mock_filter.return_value.first.return_value = turn
        mock_retrieve.return_value = b"ID3" + b"\x00" * 16

        response = voice_turn_audio(
            self.request(user),
            self.session_id,
            self.request_id,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "audio/mpeg",
        )
        self.assertEqual(
            response["Cache-Control"],
            "private, no-store",
        )
        self.assertEqual(
            response["X-Content-Type-Options"],
            "nosniff",
        )

        mock_retrieve.assert_called_once_with(
            user=user,
            assistant_id=1,
            voice_request_id=self.request_id,
        )

    @patch("ai_assistant.voice.audio_api.retrieve_voice_audio")
    @patch("ai_assistant.voice.audio_api.VoiceTurn.objects.filter")
    @patch("ai_assistant.voice.audio_api._session")
    def test_missing_audio_fails_closed(
        self,
        mock_session,
        mock_filter,
        mock_retrieve,
    ):
        user = Mock()
        user.is_authenticated = True

        session = Mock()
        session.assistant_id = 1
        mock_session.return_value = session

        turn = Mock()
        turn.state = VoiceTurn.State.COMPLETED
        turn.assistant_message_id = 10
        turn.request_id = self.request_id

        mock_filter.return_value.first.return_value = turn
        mock_retrieve.return_value = None

        response = voice_turn_audio(
            self.request(user),
            self.session_id,
            self.request_id,
        )

        self.assertEqual(response.status_code, 503)
