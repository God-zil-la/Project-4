import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import RequestFactory, SimpleTestCase

from ai_assistant.voice import audio_api
from ai_assistant.voice.models import VoiceTurn


class Step258ARealMP3Tests(SimpleTestCase):

    def setUp(self):
        self.audio = Path(
            os.environ["U63_STEP258A_MP3"]
        ).read_bytes()

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
            request_id=uuid4(),
        )

        self.factory = RequestFactory()

    def deliver(self):
        request = self.factory.get("/api/voice/test/audio/")
        request.user = self.user

        with (
            patch.object(
                audio_api,
                "_session",
                return_value=self.session,
            ),
            patch.object(
                audio_api,
                "_uuid",
                return_value=self.turn.request_id,
            ),
            patch.object(
                audio_api.VoiceTurn.objects,
                "filter",
            ) as query,
            patch.object(
                audio_api,
                "retrieve_voice_audio",
                return_value=self.audio,
            ),
        ):
            query.return_value.first.return_value = self.turn

            return audio_api.voice_turn_audio(
                request,
                uuid4(),
                self.turn.request_id,
            )

    def test_01_real_mp3_is_accepted(self):
        response = self.deliver()
        self.assertEqual(response.status_code, 200)

    def test_02_audio_bytes_remain_identical(self):
        response = self.deliver()
        self.assertEqual(response.content, self.audio)

    def test_03_correct_mime_type(self):
        response = self.deliver()
        self.assertEqual(
            response["Content-Type"],
            "audio/mpeg",
        )

    def test_04_private_cache_policy(self):
        response = self.deliver()
        self.assertEqual(
            response["Cache-Control"],
            "private, no-store",
        )

    def test_05_audio_is_not_empty(self):
        self.assertGreater(len(self.audio), 1000)

    def test_06_completed_turn_required(self):
        self.turn.state = VoiceTurn.State.SYNTHESIZING
        response = self.deliver()
        self.assertEqual(response.status_code, 409)