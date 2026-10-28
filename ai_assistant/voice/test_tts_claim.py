import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.chat_service import _save_chat_exchange
from ai_assistant.bots.models import Bot, Conversation

from .models import VoiceTurn
from .service import (
    VoiceAccessDenied,
    VoiceConflict,
    advance_turn,
    claim_ai_dispatch,
    claim_tts_dispatch,
    reserve_turn,
    save_transcript,
    start_session,
)


class TTSClaimTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="u63_tts_claim")
        cls.other = User.objects.create_user(username="u63_tts_claim_other")
        cls.bot = Bot.objects.create(
            owner=cls.user, name="TTS Claim Bot"
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

    def claim(self, **changes):
        params = dict(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
        )
        params.update(changes)
        return claim_tts_dispatch(**params)

    def save_answer(self):
        advance_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            expected=VoiceTurn.State.CREATED,
            target=VoiceTurn.State.TRANSCRIBING,
        )
        save_transcript(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            transcript="Hello",
        )
        claim_ai_dispatch(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
        )
        _save_chat_exchange(
            conversation=self.conversation,
            bot=self.bot,
            user=self.user,
            user_message="Hello",
            assistant_message="Hello back",
            voice_turn_id=self.turn.pk,
        )

    def test_claim_once(self):
        self.save_answer()
        turn, claimed = self.claim()
        self.assertTrue(claimed)
        self.assertEqual(turn.state, VoiceTurn.State.SYNTHESIZING)

        turn, claimed_again = self.claim()
        self.assertFalse(claimed_again)
        self.assertEqual(turn.state, VoiceTurn.State.SYNTHESIZING)

    def test_claim_without_answer_rejected(self):
        with self.assertRaises(VoiceConflict):
            self.claim()

    def test_foreign_user_rejected(self):
        self.save_answer()
        with self.assertRaises(VoiceAccessDenied):
            self.claim(user=self.other)
