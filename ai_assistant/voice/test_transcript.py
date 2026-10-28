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
    save_transcript,
    start_session,
)


class TranscriptTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="u63_transcript_owner")
        cls.other = User.objects.create_user(username="u63_transcript_other")
        cls.bot = Bot.objects.create(
            owner=cls.user, name="Transcript Bot"
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
        reserve_turn(
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

    def save(self, **changes):
        args = dict(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            transcript="Hello AI",
        )
        args.update(changes)
        return save_transcript(**args)

    def test_saves_transcript(self):
        turn, created = self.save()
        self.assertTrue(created)
        self.assertEqual(turn.transcript, "Hello AI")
        self.assertEqual(turn.state, VoiceTurn.State.TRANSCRIBED)

    def test_duplicate_transcript_is_idempotent(self):
        self.save()
        turn, created = self.save()
        self.assertFalse(created)
        self.assertEqual(turn.transcript, "Hello AI")

    def test_conflicting_transcript_rejected(self):
        self.save()
        with self.assertRaises(VoiceConflict):
            self.save(transcript="Different words")

    def test_foreign_user_rejected(self):
        with self.assertRaises(VoiceAccessDenied):
            self.save(user=self.other)

    def test_empty_transcript_rejected(self):
        with self.assertRaises(VoiceConflict):
            self.save(transcript="   ")

    def test_too_long_transcript_rejected(self):
        with self.assertRaises(VoiceConflict):
            self.save(transcript="a" * 10001)
