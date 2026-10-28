import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.models import Bot, Conversation
from .models import VoiceTurn
from .service import (
    VoiceAccessDenied,
    advance_turn,
    claim_ai_dispatch,
    reserve_turn,
    start_session,
)


class AiDispatchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="u63_dispatch_owner")
        cls.other = User.objects.create_user(username="u63_dispatch_other")
        cls.bot = Bot.objects.create(
            owner=cls.user, name="U63 Dispatch Bot"
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

        advance_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            expected=VoiceTurn.State.CREATED,
            target=VoiceTurn.State.TRANSCRIBING,
        )

        advance_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            expected=VoiceTurn.State.TRANSCRIBING,
            target=VoiceTurn.State.TRANSCRIBED,
        )

    def test_first_dispatch_claim_succeeds(self):
        turn, claimed = claim_ai_dispatch(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
        )
        self.assertTrue(claimed)
        self.assertEqual(turn.state, VoiceTurn.State.PROCESSING)

    def test_duplicate_dispatch_is_not_claimed(self):
        args = dict(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
        )

        claim_ai_dispatch(**args)
        turn, claimed = claim_ai_dispatch(**args)

        self.assertFalse(claimed)
        self.assertEqual(turn.state, VoiceTurn.State.PROCESSING)

    def test_foreign_user_cannot_dispatch(self):
        with self.assertRaises(VoiceAccessDenied):
            claim_ai_dispatch(
                user=self.other,
                session_id=self.session.public_id,
                request_id=self.request_id,
            )

    def test_dispatch_before_transcription_is_blocked(self):
        new_id = uuid.uuid4()

        reserve_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=new_id,
            audio_sha256="b" * 64,
        )

        _, claimed = claim_ai_dispatch(
            user=self.user,
            session_id=self.session.public_id,
            request_id=new_id,
        )
        self.assertFalse(claimed)
