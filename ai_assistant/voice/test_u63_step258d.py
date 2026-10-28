"""U6.3 step 258D: real authorization integration.

Uses Django test database, actual U6.2 authorization,
and isolated MP3 storage. No paid calls or R2.
"""

import os
from pathlib import Path
from unittest.mock import patch

from django.apps import apps
from django.test import RequestFactory

from ai_assistant.tts.authorization import authorize
from ai_assistant.tts.errors import AuthorizationDenied
from ai_assistant.tts.audio_retrieval import retrieve_audio
from ai_assistant.voice import audio_api
from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.test_u63_step254 import Step254RealDatabaseTests


class MemoryStore:
    def __init__(self, request_id, audio):
        self.items = {request_id: audio}
        self.loads = 0

    def load(self, *, request_id):
        self.loads += 1
        return self.items.get(request_id)


class Step258DRealAuthorizationTests(Step254RealDatabaseTests):

    def setUp(self):
        super().setUp()

        self.audio = Path(
            os.environ["U63_STEP258A_MP3"]
        ).read_bytes()

        self.store = MemoryStore(self.tts_request.pk, self.audio)

        Profile = apps.get_model("accounts", "UserProfile")
        profile, _ = Profile.objects.get_or_create(user=self.user)

        # Configure a valid test entitlement through existing
        # model fields, never modify billing/authorization code.
        if hasattr(profile, "plan"):
            profile.plan = "premium"
            profile.save(update_fields=["plan"])
        else:
            self.skipTest(
                "Profile has no writable plan field; "
                "test entitlement setup must be inspected."
            )

    def test_09_owner_has_real_authorization(self):
        self.assertEqual(
            authorize(self.user, self.bot.pk),
            self.user.pk,
        )

    def test_10_other_user_is_denied(self):
        with self.assertRaises(AuthorizationDenied):
            authorize(self.other_user, self.bot.pk)

    def test_11_real_authorized_mp3_retrieval(self):
        audio = retrieve_audio(
            user=self.user,
            assistant_id=self.bot.pk,
            request_id=self.request_id,
            store=self.store,
        )

        self.assertEqual(audio, self.audio)
        self.assertEqual(self.store.loads, 1)

    def test_12_real_authorized_http_delivery(self):
        self.turn.state = VoiceTurn.State.COMPLETED
        self.turn.save(update_fields=["state"])

        request = RequestFactory().get("/api/voice/test/audio/")
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
        self.assertEqual(self.store.loads, 1)

    def test_13_real_authorization_rejects_other_http_user(self):
        self.turn.state = VoiceTurn.State.COMPLETED
        self.turn.save(update_fields=["state"])

        request = RequestFactory().get("/api/voice/test/audio/")
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
        self.assertEqual(self.store.loads, 0)
