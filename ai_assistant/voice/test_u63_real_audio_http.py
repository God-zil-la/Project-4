import inspect
import tempfile
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from django.test import RequestFactory, override_settings

from . import test_u63_step254 as existing
from .audio_api import voice_turn_audio
from .local_audio_store import LocalVoiceAudioStore
from .models import VoiceTurn


def find_fixture_class():
    candidates = []

    for name, value in vars(existing).items():
        if not inspect.isclass(value):
            continue

        if value.__module__ != existing.__name__:
            continue

        if not hasattr(value, "setUp"):
            continue

        source = inspect.getsource(value.setUp)

        if (
            "VoiceSession.objects.create" in source
            and "VoiceTurn.objects.create" in source
            and "TTSRequest.objects.create" in source
        ):
            candidates.append(value)

    if len(candidates) != 1:
        raise RuntimeError(
            "Expected exactly one existing database fixture class; "
            f"found {[c.__name__ for c in candidates]}"
        )

    return candidates[0]


Fixture = find_fixture_class()


class U63RealAudioHTTPIntegrationTests(Fixture):


    def setUp(self):
        super().setUp()
        from django.utils import timezone
        from datetime import timedelta

        profile = self.user.profile
        profile.complimentary_plan = "premium"
        profile.complimentary_until = (
            timezone.now() + timedelta(hours=1)
        )
        profile.save(
            update_fields=[
                "complimentary_plan",
                "complimentary_until",
            ]
        )
        self.assertEqual(profile.effective_plan, "premium")

    def test_real_mp3_http_delivery(self):
        audio = b"\xff\xfb\x90\x64" + b"\x00" * 512

        with tempfile.TemporaryDirectory() as directory:
            with override_settings(DEBUG=True):
                with patch.dict(
                    "os.environ",
                    {"U63_LOCAL_LIVE_VOICE_ENABLED": "true"},
                ):
                    store = LocalVoiceAudioStore(
                        user_id=self.user.pk
                    )
                    store.root = (
                        Path(directory) / str(self.user.pk)
                    )

                    with patch(
                        "ai_assistant.voice.audio_store_bridge."
                        "build_voice_audio_store",
                        return_value=store,
                    ):

                        store.save(
                            request_id=self.tts_request.pk,
                            audio=audio,
                        )

                        self.turn.state = VoiceTurn.State.COMPLETED
                        self.turn.save(update_fields=["state"])

                        request = RequestFactory().get(
                            "/u63/test/audio/"
                        )
                        request.user = self.user

                        from ai_assistant.tts.audio_retrieval import (
                            authorize_audio_request,
                            retrieve_audio,
                        )

                        print("\n=== U6.3 AUTHORIZATION DIAGNOSTIC ===")
                        print("Owner ID:", self.user.pk)
                        print("Assistant ID:", self.bot.pk)
                        print("Voice request ID:", self.request_id)
                        print("TTS row ID:", self.tts_request.pk)
                        print("TTS state:", self.tts_request.state)

                        print("TTS request UUID:", self.tts_request.request_id)
                        print("UUID match:", self.request_id == self.tts_request.request_id)
                        print("Account owner ID:", self.tts_request.account.user_id)
                        print("Assistant match:", self.bot.pk == self.tts_request.assistant_id)

                        from ai_assistant.tts.models import TTSRequest

                        print(
                            "Exact DB match:",
                            TTSRequest.objects.filter(
                                account__user_id=self.user.pk,
                                assistant_id=self.bot.pk,
                                request_id=self.request_id,
                            ).count(),
                        )


                        try:
                            authorized = authorize_audio_request(
                                user=self.user,
                                assistant_id=self.bot.pk,
                                request_id=self.request_id,
                            )
                            print("AUTHORIZATION: PASSED")
                            print("Authorized row ID:", authorized.pk)

                            retrieved = retrieve_audio(
                                user=self.user,
                                assistant_id=self.bot.pk,
                                request_id=self.request_id,
                                store=store,
                            )
                            print(
                                "DIRECT AUDIO RETRIEVAL:",
                                "AVAILABLE" if retrieved is not None
                                else "MISSING",
                            )

                        except Exception as exc:
                            print("AUTHORIZATION: FAILED")
                            print("Exception type:", type(exc).__name__)
                            print("Exception message:", str(exc))

                        print("=== END DIAGNOSTIC ===\n")

                        response = voice_turn_audio(
                            request,
                            self.session.public_id,
                            self.request_id,
                        )

                        self.assertEqual(
                            response.status_code,
                            200,
                            response.content,
                        )
                        self.assertEqual(
                            response.content,
                            audio,
                        )
                        self.assertEqual(
                            response["Content-Type"],
                            "audio/mpeg",
                        )
                        self.assertEqual(
                            response["Cache-Control"],
                            "private, no-store",
                        )
