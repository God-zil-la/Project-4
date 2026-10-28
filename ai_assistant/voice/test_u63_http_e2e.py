import uuid
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.utils import timezone

from ai_assistant.bots.chat_service import _save_chat_exchange
from ai_assistant.bots.models import Bot, ChatMessage, Conversation
from ai_assistant.stt.normalizer import ServerPeriodEvidence, reserve_normalized
from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.service import start_session
from ai_assistant.voice.test_upload_api import sample_wav
from ai_assistant.voice.trusted_http_dispatch import TrustedVoiceDependencies
from django.core.files.uploadedfile import SimpleUploadedFile


class U63HTTPFullE2ETests(TransactionTestCase):
    def test_http_stt_ai_tts_and_duplicate_protection(self):
        user = get_user_model().objects.create_user(
            username="u63_http_e2e_owner"
        )
        bot = Bot.objects.create(
            owner=user,
            name="U6.3 E2E Assistant",
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
            user.pk,
            "stripe",
            "sandbox",
            "u63-e2e-subscription",
            "u63-e2e-cycle",
            "premium",
            now - timedelta(days=15),
            now + timedelta(days=15),
            now,
            True,
            True,
            "ordinary_monthly",
        )

        transcriber = Mock(return_value="Hej från Live Voice")
        synthesizer = Mock(return_value=SimpleNamespace(
            state="succeeded",
            audio=b"mock-audio",
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
        url = f"/api/live-voice/{session.public_id}/upload/"

        def upload():
            return SimpleUploadedFile(
                "voice.wav",
                sample_wav(),
                content_type="audio/wav",
            )

        self.client.force_login(user)

        with patch(
            "ai_assistant.voice.upload_api.resolve_http_voice_dependencies",
            return_value=dependencies,
        ), patch(
            "ai_assistant.voice.ai_adapter.process_bot_message",
            side_effect=fake_chat,
        ) as chat, patch(
            "ai_assistant.voice.tts_adapter.synthesize_saved_response",
            synthesizer,
        ):
            response = self.client.post(
                url,
                {
                    "audio": upload(),
                    "request_id": request_id,
                },
            )

            self.assertEqual(
                response.status_code,
                200,
                response.content.decode(),
            )

            turn = VoiceTurn.objects.get(
                session=session,
                request_id=request_id,
            )
            self.assertEqual(
                turn.state,
                VoiceTurn.State.COMPLETED,
            )
            self.assertIsNotNone(turn.assistant_message_id)

            self.assertEqual(
                ChatMessage.objects.filter(
                    conversation=conversation
                ).count(),
                2,
            )

            self.assertEqual(transcriber.call_count, 1)
            self.assertEqual(chat.call_count, 1)
            self.assertEqual(synthesizer.call_count, 1)

            duplicate = self.client.post(
                url,
                {
                    "audio": upload(),
                    "request_id": request_id,
                },
            )

            self.assertEqual(duplicate.status_code, 409)
            self.assertEqual(transcriber.call_count, 1)
            self.assertEqual(chat.call_count, 1)
            self.assertEqual(synthesizer.call_count, 1)
