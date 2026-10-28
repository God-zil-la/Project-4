"""U6.3 step 258C: real MP3 storage and HTTP delivery.

Isolated Django test database and in-memory audio storage.
No external R2, paid synthesis, or production changes.
"""

import os
from pathlib import Path
from unittest.mock import patch

from django.test import RequestFactory

from ai_assistant.tts.audio_retrieval import retrieve_audio
from ai_assistant.voice import audio_api
from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.real_audio_recovery import recover_real_voice_audio
from ai_assistant.voice.test_u63_step254 import Step254RealDatabaseTests


class MemoryAudioStore:
    def __init__(self):
        self.items = {}
        self.load_count = 0

    def load(self, *, request_id):
        self.load_count += 1
        return self.items.get(request_id)


class Step258CRealStorageTests(Step254RealDatabaseTests):

    def setUp(self):
        super().setUp()

        self.audio = Path(
            os.environ["U63_STEP258A_MP3"]
        ).read_bytes()

        self.store = MemoryAudioStore()
        self.store.items[self.tts_request.pk] = self.audio
        self.factory = RequestFactory()

        # Test-only authorization boundary. Keep real retrieval,
        # repeated authorization checks and store.load() execution.
        from ai_assistant.tts.errors import AuthorizationDenied

        def isolated_authorization(*, user, assistant_id, request_id):
            if (
                user.pk != self.user.pk
                or assistant_id != self.bot.pk
                or request_id != self.tts_request.request_id
            ):
                raise AuthorizationDenied("tts_denied")
            return self.tts_request

        auth_patch = patch(
            "ai_assistant.tts.audio_retrieval.authorize_audio_request",
            side_effect=isolated_authorization,
        )
        auth_patch.start()
        self.addCleanup(auth_patch.stop)

    def test_09_real_store_load_returns_identical_mp3(self):
        result = retrieve_audio(
            user=self.user,
            assistant_id=self.bot.pk,
            request_id=self.tts_request.request_id,
            store=self.store,
        )

        self.assertEqual(result, self.audio)
        self.assertEqual(self.store.load_count, 1)

    def test_10_wrong_user_cannot_read_stored_mp3(self):
        with self.assertRaises(Exception):
            retrieve_audio(
                user=self.other_user,
                assistant_id=self.bot.pk,
                request_id=self.tts_request.request_id,
                store=self.store,
            )

        self.assertEqual(self.store.load_count, 0)

    def test_11_recovery_uses_real_retrieval(self):
        with patch(
            "ai_assistant.voice.real_audio_recovery."
            "get_assistant_message",
            return_value=self.message.message,
        ):
            result = recover_real_voice_audio(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                audio_store=self.store,
            )

        self.turn.refresh_from_db()

        self.assertTrue(result.audio_available)
        self.assertEqual(
            self.turn.state,
            VoiceTurn.State.COMPLETED,
        )
        self.assertEqual(self.store.load_count, 1)

    def test_12_repeated_recovery_does_not_resynthesize(self):
        with patch(
            "ai_assistant.voice.real_audio_recovery."
            "get_assistant_message",
            return_value=self.message.message,
        ):
            first = recover_real_voice_audio(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                audio_store=self.store,
            )

            second = recover_real_voice_audio(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                audio_store=self.store,
            )

        self.assertTrue(first.audio_available)
        self.assertTrue(second.audio_available)
        self.assertEqual(self.store.load_count, 2)

    def test_13_authenticated_http_delivers_identical_mp3(self):
        self.turn.state = VoiceTurn.State.COMPLETED
        self.turn.save(update_fields=["state"])

        request = self.factory.get("/api/voice/test/audio/")
        request.user = self.user

        with patch(
            "ai_assistant.voice.audio_store_bridge."
            "build_voice_audio_store",
            return_value=self.store,
        ):
            response = audio_api.voice_turn_audio(
                request,
                self.session.public_id,
                self.request_id,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.audio)
        self.assertEqual(response["Content-Type"], "audio/mpeg")
        self.assertEqual(
            response["Cache-Control"],
            "private, no-store",
        )
        self.assertEqual(
            response["X-Content-Type-Options"],
            "nosniff",
        )
        self.assertEqual(self.store.load_count, 1)

    def test_14_wrong_user_http_cannot_receive_mp3(self):
        self.turn.state = VoiceTurn.State.COMPLETED
        self.turn.save(update_fields=["state"])

        request = self.factory.get("/api/voice/test/audio/")
        request.user = self.other_user

        with patch(
            "ai_assistant.voice.audio_store_bridge."
            "build_voice_audio_store",
            return_value=self.store,
        ):
            response = audio_api.voice_turn_audio(
                request,
                self.session.public_id,
                self.request_id,
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.store.load_count, 0)

    def test_15_unfinished_turn_cannot_deliver_mp3(self):
        request = self.factory.get("/api/voice/test/audio/")
        request.user = self.user

        with patch(
            "ai_assistant.voice.audio_store_bridge."
            "build_voice_audio_store",
            return_value=self.store,
        ):
            response = audio_api.voice_turn_audio(
                request,
                self.session.public_id,
                self.request_id,
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.store.load_count, 0)
