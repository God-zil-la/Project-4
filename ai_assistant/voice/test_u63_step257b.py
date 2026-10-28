from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from django.test import RequestFactory

from ai_assistant.voice import audio_api
from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.service import VoiceAccessDenied


class Step257BAudioDeliveryTests(TestCase):

    def setUp(self):
        self.factory = RequestFactory()
        self.session_id = uuid4()
        self.request_id = uuid4()
        self.user = SimpleNamespace(
            pk=101,
            is_authenticated=True,
        )
        self.session = SimpleNamespace(
            assistant_id=201,
        )
        self.turn = SimpleNamespace(
            state=VoiceTurn.State.COMPLETED,
            assistant_message_id=301,
            request_id=self.request_id,
        )

    def request(self, user=None):
        request = self.factory.get(
            "/api/voice/test/audio/"
        )
        request.user = self.user if user is None else user
        return request

    def execute(self, *, audio=b"ID3" + b"\x00" * 32,
                state=None, user=None, denied=False):
        if state is not None:
            self.turn.state = state

        with (
            patch.object(
                audio_api,
                "_session",
                side_effect=(
                    VoiceAccessDenied("denied")
                    if denied else None
                ),
                return_value=self.session,
            ) as session_lookup,
            patch.object(
                audio_api,
                "_uuid",
                return_value=self.request_id,
            ),
            patch.object(
                audio_api.VoiceTurn.objects,
                "filter",
            ) as query,
            patch.object(
                audio_api,
                "retrieve_voice_audio",
                return_value=audio,
            ) as retrieve,
        ):
            query.return_value.first.return_value = self.turn

            response = audio_api.voice_turn_audio(
                self.request(user),
                self.session_id,
                self.request_id,
            )

            return (
                response,
                session_lookup.call_count,
                retrieve.call_count,
            )

    def test_01_valid_mp3_is_delivered(self):
        response, sessions, retrievals = self.execute()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "audio/mpeg",
        )
        self.assertEqual(retrievals, 1)

    def test_02_anonymous_user_is_denied(self):
        anonymous = SimpleNamespace(
            is_authenticated=False,
        )
        response, sessions, retrievals = self.execute(
            user=anonymous
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(retrievals, 0)

    def test_03_foreign_session_is_denied(self):
        response, sessions, retrievals = self.execute(
            denied=True
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(retrievals, 0)

    def test_04_incomplete_turn_is_denied(self):
        response, sessions, retrievals = self.execute(
            state=VoiceTurn.State.SYNTHESIZING
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(retrievals, 0)

    def test_05_invalid_mp3_is_rejected(self):
        response, sessions, retrievals = self.execute(
            audio=b"NOT-AN-MP3"
        )
        self.assertEqual(response.status_code, 503)

    def test_06_missing_audio_is_unavailable(self):
        response, sessions, retrievals = self.execute(
            audio=None
        )
        self.assertEqual(response.status_code, 503)

    def test_07_audio_is_not_publicly_cached(self):
        response, sessions, retrievals = self.execute()
        self.assertEqual(
            response["Cache-Control"],
            "private, no-store",
        )
        self.assertEqual(
            response["X-Content-Type-Options"],
            "nosniff",
        )

    def test_08_audio_bytes_are_preserved(self):
        mp3 = b"ID3" + b"\x01" * 128
        response, sessions, retrievals = self.execute(
            audio=mp3
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, mp3)