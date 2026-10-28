import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from .service import (
    VoiceAccessDenied,
    VoiceConflict,
    _uuid,
    reserve_turn,
    start_session,
)


class VoiceIdentityTests(TestCase):
    def test_invalid_request_identifier_is_rejected(self):
        with self.assertRaises(VoiceAccessDenied):
            _uuid("not-a-uuid")

    def test_foreign_conversation_is_rejected(self):
        user = SimpleNamespace(pk=1)
        assistant = SimpleNamespace(pk=10, owner_id=1)
        conversation = SimpleNamespace(
            pk=20,
            user_id=2,
            bot_id=10,
            is_widget=False,
            discord_integration_id=None,
        )

        with self.assertRaises(VoiceAccessDenied):
            start_session(
                user=user,
                assistant=assistant,
                conversation=conversation,
            )

    @patch("ai_assistant.voice.service._session")
    def test_invalid_audio_fingerprint_is_rejected(self, session_mock):
        session_mock.return_value = SimpleNamespace(pk=1)

        with self.assertRaises(VoiceAccessDenied):
            reserve_turn(
                user=SimpleNamespace(pk=1),
                session_id=uuid.uuid4(),
                request_id=uuid.uuid4(),
                audio_sha256="invalid",
            )

    @patch("ai_assistant.voice.service.VoiceTurn.objects")
    @patch("ai_assistant.voice.service._session")
    def test_same_request_with_different_audio_is_rejected(
        self, session_mock, manager
    ):
        session_mock.return_value = SimpleNamespace(pk=1)
        manager.filter.return_value.first.return_value = SimpleNamespace(
            audio_sha256="a" * 64
        )

        with self.assertRaises(VoiceConflict):
            reserve_turn(
                user=SimpleNamespace(pk=1),
                session_id=uuid.uuid4(),
                request_id=uuid.uuid4(),
                audio_sha256="b" * 64,
            )

        manager.create.assert_not_called()

    @patch("ai_assistant.voice.service.VoiceTurn.objects")
    @patch("ai_assistant.voice.service._session")
    def test_duplicate_request_reuses_existing_turn(
        self, session_mock, manager
    ):
        session_mock.return_value = SimpleNamespace(pk=1)
        existing = SimpleNamespace(audio_sha256="a" * 64)
        manager.filter.return_value.first.return_value = existing

        turn, created = reserve_turn(
            user=SimpleNamespace(pk=1),
            session_id=uuid.uuid4(),
            request_id=uuid.uuid4(),
            audio_sha256="a" * 64,
        )

        self.assertIs(turn, existing)
        self.assertFalse(created)
        manager.create.assert_not_called()
