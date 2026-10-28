import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.models import Bot, Conversation
from ai_assistant.stt.models import STTAccount, STTReservation
from .models import VoiceTurn
from .service import (
    VoiceAccessDenied,
    VoiceConflict,
    advance_turn,
    reserve_turn,
    start_session,
)
from .stt_adapter import accept_stt_result


class STTAdapterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="u63_stt_adapter_owner"
        )
        cls.other = User.objects.create_user(
            username="u63_stt_adapter_other"
        )
        cls.bot = Bot.objects.create(
            owner=cls.user,
            name="STT Integration Bot",
        )
        cls.conversation = Conversation.objects.create(
            user=cls.user,
            bot=cls.bot,
        )

    def setUp(self):
        self.session = start_session(
            user=self.user,
            assistant=self.bot,
            conversation=self.conversation,
        )
        self.request_id = uuid.uuid4()
        self.audio_hash = "a" * 64

        self.turn, _ = reserve_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            audio_sha256=self.audio_hash,
        )

        advance_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            expected=VoiceTurn.State.CREATED,
            target=VoiceTurn.State.TRANSCRIBING,
        )

    def accept(self, **changes):
        args = {
            "user": self.user,
            "session_id": self.session.public_id,
            "request_id": self.request_id,
            "reservation_id": 123,
            "transcript": "Hello from STT",
        }
        args.update(changes)
        return accept_stt_result(**args)

    def _reservation(self, **changes):
        reservation = STTReservation(
            id=123,
            account=STTAccount(user=self.user),
            request_id=self.request_id,
            audio_sha256=self.audio_hash,
            assistant_id=self.bot.pk,
            state="consumed",
        )
        for key, value in changes.items():
            setattr(reservation, key, value)
        return reservation

    def test_successful_reservation_saves_transcript(self):
        with patch(
            "ai_assistant.voice.stt_adapter.STTReservation.objects.filter"
        ) as query:
            query.return_value.first.return_value = self._reservation()
            turn, created = self.accept()

        self.assertTrue(created)
        self.assertEqual(turn.transcript, "Hello from STT")
        self.assertEqual(turn.state, VoiceTurn.State.TRANSCRIBED)

    def test_duplicate_result_is_idempotent(self):
        with patch(
            "ai_assistant.voice.stt_adapter.STTReservation.objects.filter"
        ) as query:
            query.return_value.first.return_value = self._reservation()
            self.accept()
            turn, created = self.accept()

        self.assertFalse(created)
        self.assertEqual(turn.transcript, "Hello from STT")

    def test_unsettled_reservation_rejected(self):
        with patch(
            "ai_assistant.voice.stt_adapter.STTReservation.objects.filter"
        ) as query:
            query.return_value.first.return_value = self._reservation(
                state="uncertain"
            )
            with self.assertRaises(VoiceConflict):
                self.accept()

    def test_wrong_audio_hash_rejected(self):
        with patch(
            "ai_assistant.voice.stt_adapter.STTReservation.objects.filter"
        ) as query:
            query.return_value.first.return_value = self._reservation(
                audio_sha256="b" * 64
            )
            with self.assertRaises(VoiceConflict):
                self.accept()

    def test_wrong_assistant_rejected(self):
        with patch(
            "ai_assistant.voice.stt_adapter.STTReservation.objects.filter"
        ) as query:
            query.return_value.first.return_value = self._reservation(
                assistant_id=self.bot.pk + 1000
            )
            with self.assertRaises(VoiceConflict):
                self.accept()

    def test_foreign_user_rejected(self):
        with self.assertRaises(VoiceAccessDenied):
            self.accept(user=self.other)

    def test_missing_reservation_rejected(self):
        with patch(
            "ai_assistant.voice.stt_adapter.STTReservation.objects.filter"
        ) as query:
            query.return_value.first.return_value = None
            with self.assertRaises(VoiceAccessDenied):
                self.accept()
