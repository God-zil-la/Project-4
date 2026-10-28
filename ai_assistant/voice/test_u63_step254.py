"""U6.3 step 254: real ORM recovery integration tests.

No paid provider calls, no external R2 access.
Only the U6.3 test module is added.
"""

from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TransactionTestCase

from ai_assistant.bots.models import Bot, ChatMessage
from ai_assistant.voice.models import VoiceSession, VoiceTurn
from ai_assistant.voice.real_audio_recovery import (
    recover_real_voice_audio,
    RealAudioRecoveryError,
)
from ai_assistant.voice.real_tts_identity import (
    validate_real_tts_identity,
)
from ai_assistant.tts.models import TTSAccount, TTSRequest


class Step254RealDatabaseTests(TransactionTestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="u63_step254_owner",
            password="local-test-only",
        )

        self.other_user = User.objects.create_user(
            username="u63_step254_other",
            password="local-test-only",
        )

        self.bot = Bot.objects.create(
            owner=self.user,
            name="U63 Recovery Test",
            description="Isolated test assistant",
        )

        conversation_model = VoiceSession._meta.get_field(
            "conversation"
        ).remote_field.model

        conversation_fields = {
            field.name: field
            for field in conversation_model._meta.fields
        }

        kwargs = {}

        if "user" in conversation_fields:
            kwargs["user"] = self.user

        if "bot" in conversation_fields:
            kwargs["bot"] = self.bot

        if "assistant" in conversation_fields:
            kwargs["assistant"] = self.bot

        for field in conversation_model._meta.fields:
            if field.primary_key:
                continue

            if field.name in kwargs:
                continue

            if field.null or field.has_default():
                continue

            if getattr(field, "auto_now", False):
                continue

            if getattr(field, "auto_now_add", False):
                continue

            if field.name in ("title", "name"):
                kwargs[field.name] = "U63 Test Conversation"
                continue

            raise AssertionError(
                "Conversation requires unsupported field: "
                + field.name
            )

        self.conversation = conversation_model.objects.create(
            **kwargs
        )

        self.session = VoiceSession.objects.create(
            user=self.user,
            assistant=self.bot,
            conversation=self.conversation,
        )

        self.message = ChatMessage.objects.create(
            conversation=self.conversation,
            bot=self.bot,
            user=self.user,
            sender="assistant",
            message="Detta är ett sparat testsvar.",
        )

        self.request_id = uuid4()

        self.turn = VoiceTurn.objects.create(
            session=self.session,
            request_id=self.request_id,
            audio_sha256="a" * 64,
            state=VoiceTurn.State.SYNTHESIZING,
            transcript="Hej!",
            assistant_message=self.message,
        )

        self.account = TTSAccount.objects.create(
            user=self.user
        )

        key, fingerprint = validate_real_tts_identity(
            text=self.message.message,
            assistant_id=self.bot.pk,
            conversation_id=self.conversation.public_id,
            message_id=self.message.pk,
            request_id=self.request_id,
        )

        self.tts_request = TTSRequest.objects.create(
            account=self.account,
            assistant_id=self.bot.pk,
            request_id=key,
            fingerprint=fingerprint,
            state="succeeded",
        )

        self.audio_store = object()

    def test_01_complete_recovery_from_saved_audio(self):
        fake_mp3 = (
            b"\xff\xfb\x90\x64"
            + b"\x00" * 512
        )

        with (
            patch(
                "ai_assistant.voice.real_audio_recovery."
                "get_assistant_message",
                return_value=self.message.message,
            ),
            patch(
                "ai_assistant.voice.real_audio_recovery."
                "retrieve_audio",
                return_value=fake_mp3,
            ) as retrieve,
            patch(
                "ai_assistant.voice.real_audio_recovery."
                "validate_live_mp3",
            ),
        ):
            result = recover_real_voice_audio(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                audio_store=self.audio_store,
            )

        self.turn.refresh_from_db()

        self.assertTrue(result.audio_available)
        self.assertEqual(
            self.turn.state,
            VoiceTurn.State.COMPLETED,
        )
        retrieve.assert_called_once()

    def test_02_recovery_is_idempotent(self):
        self.turn.state = VoiceTurn.State.COMPLETED
        self.turn.save(update_fields=["state"])

        with (
            patch(
                "ai_assistant.voice.real_audio_recovery."
                "get_assistant_message",
                return_value=self.message.message,
            ),
            patch(
                "ai_assistant.voice.real_audio_recovery."
                "retrieve_audio",
                return_value=b"\xff\xfb\x90\x64" + b"\x00" * 512,
            ),
            patch(
                "ai_assistant.voice.real_audio_recovery."
                "validate_live_mp3",
            ),
        ):
            first = recover_real_voice_audio(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                audio_store=self.audio_store,
            )

            second = recover_real_voice_audio(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                audio_store=self.audio_store,
            )

        self.assertTrue(first.audio_available)
        self.assertTrue(second.audio_available)

        self.turn.refresh_from_db()
        self.assertEqual(
            self.turn.state,
            VoiceTurn.State.COMPLETED,
        )

    def test_03_missing_audio_does_not_complete_turn(self):
        with (
            patch(
                "ai_assistant.voice.real_audio_recovery."
                "get_assistant_message",
                return_value=self.message.message,
            ),
            patch(
                "ai_assistant.voice.real_audio_recovery."
                "retrieve_audio",
                return_value=None,
            ),
        ):
            result = recover_real_voice_audio(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                audio_store=self.audio_store,
            )

        self.turn.refresh_from_db()

        self.assertFalse(result.audio_available)
        self.assertEqual(
            self.turn.state,
            VoiceTurn.State.SYNTHESIZING,
        )

    def test_04_wrong_user_cannot_recover(self):
        with self.assertRaises(Exception):
            recover_real_voice_audio(
                user=self.other_user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                audio_store=self.audio_store,
            )

        self.turn.refresh_from_db()
        self.assertEqual(
            self.turn.state,
            VoiceTurn.State.SYNTHESIZING,
        )

    def test_05_duplicate_voice_request_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                VoiceTurn.objects.create(
                    session=self.session,
                    request_id=self.request_id,
                    audio_sha256="b" * 64,
                    transcript="Duplicate",
                )

        self.assertEqual(
            VoiceTurn.objects.filter(
                session=self.session,
                request_id=self.request_id,
            ).count(),
            1,
        )

    def test_06_duplicate_tts_request_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TTSRequest.objects.create(
                    account=self.account,
                    assistant_id=self.bot.pk,
                    request_id=self.request_id,
                    fingerprint="f" * 64,
                    state="pending",
                )

        self.assertEqual(
            TTSRequest.objects.filter(
                account=self.account,
                request_id=self.request_id,
            ).count(),
            1,
        )

    def test_07_answer_saved_is_not_recoverable(self):
        self.turn.state = VoiceTurn.State.ANSWER_SAVED
        self.turn.save(update_fields=["state"])

        with self.assertRaises(RealAudioRecoveryError):
            recover_real_voice_audio(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                audio_store=self.audio_store,
            )

    def test_08_unsuccessful_tts_cannot_complete_turn(self):
        self.tts_request.state = "uncertain"
        self.tts_request.save(update_fields=["state"])

        with patch(
            "ai_assistant.voice.real_audio_recovery."
            "get_assistant_message",
            return_value=self.message.message,
        ):
            result = recover_real_voice_audio(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                audio_store=self.audio_store,
            )

        self.assertFalse(result.audio_available)

        self.turn.refresh_from_db()
        self.assertEqual(
            self.turn.state,
            VoiceTurn.State.SYNTHESIZING,
        )
