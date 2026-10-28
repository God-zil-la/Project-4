import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.models import Bot, Conversation
from .models import VoiceTurn
from .service import (
    VoiceAccessDenied,
    VoiceConflict,
    advance_turn,
    reserve_turn,
    start_session,
)


class VoiceTransitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="u63_transition_owner")
        cls.stranger = User.objects.create_user(username="u63_transition_other")
        cls.bot = Bot.objects.create(
            owner=cls.user, name="Voice Transition Bot"
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

    def test_valid_transition(self):
        result = advance_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            expected=VoiceTurn.State.CREATED,
            target=VoiceTurn.State.TRANSCRIBING,
        )
        self.assertEqual(result.state, VoiceTurn.State.TRANSCRIBING)

    def test_stale_state_is_rejected(self):
        advance_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            expected=VoiceTurn.State.CREATED,
            target=VoiceTurn.State.TRANSCRIBING,
        )
        with self.assertRaises(VoiceConflict):
            advance_turn(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                expected=VoiceTurn.State.CREATED,
                target=VoiceTurn.State.TRANSCRIBING,
            )

    def test_illegal_transition_is_rejected(self):
        with self.assertRaises(VoiceConflict):
            advance_turn(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                expected=VoiceTurn.State.CREATED,
                target=VoiceTurn.State.COMPLETED,
            )

    def test_foreign_user_cannot_advance(self):
        with self.assertRaises(VoiceAccessDenied):
            advance_turn(
                user=self.stranger,
                session_id=self.session.public_id,
                request_id=self.request_id,
                expected=VoiceTurn.State.CREATED,
                target=VoiceTurn.State.TRANSCRIBING,
            )
