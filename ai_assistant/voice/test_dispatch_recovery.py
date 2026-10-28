import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.chat_service import _save_chat_exchange
from ai_assistant.bots.models import Bot, Conversation
from .models import VoiceTurn
from .service import (
    advance_turn,
    claim_ai_dispatch,
    reserve_turn,
    start_session,
)


class DispatchRecoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="u63_recovery")
        cls.bot = Bot.objects.create(
            owner=cls.user, name="Recovery Voice Bot"
        )
        cls.conversation = Conversation.objects.create(
            user=cls.user, bot=cls.bot
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
        for expected, target in (
            (VoiceTurn.State.CREATED, VoiceTurn.State.TRANSCRIBING),
            (VoiceTurn.State.TRANSCRIBING, VoiceTurn.State.TRANSCRIBED),
        ):
            advance_turn(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                expected=expected,
                target=target,
            )

    def claim(self):
        return claim_ai_dispatch(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
        )

    def test_processing_cannot_be_claimed_again(self):
        first, claimed = self.claim()
        self.assertTrue(claimed)
        self.assertEqual(first.state, VoiceTurn.State.PROCESSING)

        self.turn.refresh_from_db()
        second, claimed_again = self.claim()

        self.assertFalse(claimed_again)
        self.assertEqual(second.state, VoiceTurn.State.PROCESSING)

    def test_saved_answer_cannot_be_dispatched_again(self):
        self.claim()

        message_id = _save_chat_exchange(
            conversation=self.conversation,
            bot=self.bot,
            user=self.user,
            user_message="Voice input",
            assistant_message="Voice answer",
            voice_turn_id=self.turn.pk,
        )

        turn, claimed = self.claim()

        self.assertFalse(claimed)
        self.assertEqual(turn.state, VoiceTurn.State.ANSWER_SAVED)
        self.assertEqual(turn.assistant_message_id, message_id)

    def test_uncertain_turn_is_not_retried(self):
        self.claim()
        advance_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            expected=VoiceTurn.State.PROCESSING,
            target=VoiceTurn.State.UNCERTAIN,
        )

        turn, claimed = self.claim()

        self.assertFalse(claimed)
        self.assertEqual(turn.state, VoiceTurn.State.UNCERTAIN)

    def test_reused_request_id_retains_dispatch_state(self):
        self.claim()

        existing, created = reserve_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            audio_sha256="a" * 64,
        )

        self.assertFalse(created)
        self.assertEqual(existing.pk, self.turn.pk)
        self.assertEqual(existing.state, VoiceTurn.State.PROCESSING)
