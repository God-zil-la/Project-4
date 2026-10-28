import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.models import Bot, Conversation
from .models import VoiceTurn
from .service import (
    VoiceConflict,
    advance_turn,
    claim_ai_dispatch,
    reserve_turn,
    start_session,
)


class AnswerGuardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="u63_answer_guard"
        )
        cls.bot = Bot.objects.create(
            owner=cls.user,
            name="Answer Guard Bot",
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
        self.turn, _ = reserve_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            audio_sha256="a" * 64,
        )
        for before, after in (
            (VoiceTurn.State.CREATED, VoiceTurn.State.TRANSCRIBING),
            (VoiceTurn.State.TRANSCRIBING, VoiceTurn.State.TRANSCRIBED),
        ):
            advance_turn(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                expected=before,
                target=after,
            )
        claim_ai_dispatch(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
        )

    def test_cannot_fake_saved_answer(self):
        with self.assertRaises(VoiceConflict):
            advance_turn(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                expected=VoiceTurn.State.PROCESSING,
                target=VoiceTurn.State.ANSWER_SAVED,
            )

        self.turn.refresh_from_db()
        self.assertEqual(self.turn.state, VoiceTurn.State.PROCESSING)
        self.assertIsNone(self.turn.assistant_message_id)

    def test_can_mark_processing_uncertain(self):
        turn = advance_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            expected=VoiceTurn.State.PROCESSING,
            target=VoiceTurn.State.UNCERTAIN,
        )
        self.assertEqual(turn.state, VoiceTurn.State.UNCERTAIN)
