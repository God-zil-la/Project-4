"""U6.3 HTTP upload-to-MP3 integration test. No paid providers."""

import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TransactionTestCase
from django.utils import timezone

from ai_assistant.bots.chat_service import _save_chat_exchange
from ai_assistant.bots.models import Bot, Conversation
from ai_assistant.stt.normalizer import ServerPeriodEvidence, reserve_normalized
from ai_assistant.voice.service import start_session
from ai_assistant.voice.test_upload_api import sample_wav
from ai_assistant.voice.trusted_http_dispatch import TrustedVoiceDependencies


class U63HTTPMP3E2ETests(TransactionTestCase):

    def test_upload_status_and_mp3_delivery(self):
        import os

        mp3 = Path(os.environ["U63_STEP258A_MP3"]).read_bytes()

        user = get_user_model().objects.create_user(
            username="u63_http_mp3_owner"
        )
        bot = Bot.objects.create(
            owner=user,
            name="U6.3 MP3 E2E Assistant",
        )
        conversation = Conversation.objects.create(
            user=user,
            bot=bot,
        )
        session = start_session(
            user=user,
            assistant=bot,
            conversation=conversation,
        )

        now = timezone.now()
        evidence = ServerPeriodEvidence(
            user.pk, "stripe", "sandbox",
            "u63-mp3-subscription", "u63-mp3-cycle",
            "premium",
            now - timedelta(days=15),
            now + timedelta(days=15),
            now, True, True, "ordinary_monthly",
        )

        transcriber = Mock(return_value="Hej från mikrofonen")
        synthesizer = Mock(return_value=SimpleNamespace(
            state="succeeded",
            audio=mp3,
        ))

        def fake_chat(**kwargs):
            message_id = _save_chat_exchange(
                conversation=conversation,
                bot=bot,
                user=user,
                user_message=kwargs["message"],
                assistant_message="Hej tillbaka!",
                voice_turn_id=kwargs["voice_turn_id"],
            )
            return {"assistant_message_id": message_id}

        dependencies = TrustedVoiceDependencies(
            resolve_evidence=lambda **kwargs: evidence,
            reserve_stt=reserve_normalized,
            transcribe=transcriber,
            audio_store=None,
            synthesize=None,
        )

        request_id = str(uuid.uuid4())
        base = f"/api/live-voice/{session.public_id}"

        self.client.force_login(user)

        with (
            patch(
                "ai_assistant.voice.upload_api.resolve_http_voice_dependencies",
                return_value=dependencies,
            ),
            patch(
                "ai_assistant.voice.ai_adapter.process_bot_message",
                side_effect=fake_chat,
            ),
            patch(
                "ai_assistant.voice.tts_adapter.synthesize_saved_response",
                synthesizer,
            ),
        ):
            response = self.client.post(
                f"{base}/upload/",
                {
                    "audio": SimpleUploadedFile(
                        "voice.wav",
                        sample_wav(),
                        content_type="audio/wav",
                    ),
                    "request_id": request_id,
                },
            )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(transcriber.call_count, 1)
        self.assertEqual(synthesizer.call_count, 1)

        status = self.client.get(
            f"{base}/turns/{request_id}/"
        )
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.json()["state"], "completed")
        self.assertTrue(status.json()["has_assistant_answer"])

        with patch(
            "ai_assistant.voice.audio_api.retrieve_voice_audio",
            return_value=mp3,
        ) as retrieval:
            audio_response = self.client.get(
                f"{base}/turns/{request_id}/audio/"
            )

        self.assertEqual(audio_response.status_code, 200)
        self.assertEqual(audio_response["Content-Type"], "audio/mpeg")
        self.assertEqual(audio_response.content, mp3)
        self.assertEqual(retrieval.call_count, 1)
