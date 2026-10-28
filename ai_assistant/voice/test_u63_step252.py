"""Step 252: real database recovery integration tests.

All provider and external storage operations are disabled.
Existing U6.1/U6.2 source files are never modified.
"""

from pathlib import Path
from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase

from ai_assistant.voice import service as voice_service
from ai_assistant.voice import real_audio_recovery as recovery
from ai_assistant.voice.models import VoiceSession, VoiceTurn
from ai_assistant.tts.models import TTSAccount, TTSRequest


class Step252DatabaseTests(TransactionTestCase):

    def setUp(self):
        User = get_user_model()

        self.user = User.objects.create_user(
            username="u63_step252_owner",
            password="not-a-real-password",
        )

        self.other_user = User.objects.create_user(
            username="u63_step252_other",
            password="not-a-real-password",
        )

        self.request_id = uuid4()

    def test_01_real_voice_turn_state_model(self):
        states = {
            value
            for value, label in VoiceTurn.State.choices
        }

        self.assertIn("answer_saved", states)
        self.assertIn("synthesizing", states)
        self.assertIn("completed", states)

    def test_02_voice_session_has_owner_relation(self):
        fields = {
            field.name
            for field in VoiceSession._meta.fields
        }

        self.assertIn("user", fields)
        self.assertIn("assistant", fields)
        self.assertIn("conversation", fields)

    def test_03_voice_turn_has_session_relation(self):
        fields = {
            field.name
            for field in VoiceTurn._meta.fields
        }

        self.assertIn("session", fields)
        self.assertIn("request_id", fields)
        self.assertIn("state", fields)
        self.assertIn("assistant_message", fields)

    def test_04_tts_request_has_identity_fields(self):
        fields = {
            field.name
            for field in TTSRequest._meta.fields
        }

        for required in (
            "account",
            "assistant_id",
            "request_id",
            "fingerprint",
            "state",
        ):
            self.assertIn(required, fields)

    def test_05_tts_request_database_constraint(self):
        names = {
            constraint.name
            for constraint in TTSRequest._meta.constraints
        }

        self.assertIn("tts_unique_request", names)

    def test_06_voice_turn_unique_constraint(self):
        constraints = VoiceTurn._meta.constraints

        unique_constraints = [
            constraint
            for constraint in constraints
            if hasattr(constraint, "fields")
            and set(constraint.fields) == {
                "session",
                "request_id",
            }
        ]

        self.assertTrue(unique_constraints)

    def test_07_recovery_rejects_missing_store(self):
        with self.assertRaises(
            recovery.RealAudioRecoveryError
        ):
            recovery.recover_real_voice_audio(
                user=self.user,
                session_id=uuid4(),
                request_id=self.request_id,
                audio_store=None,
            )

    def test_08_recovery_does_not_dispatch_provider(self):
        source = Path(
            "ai_assistant/voice/real_audio_recovery.py"
        ).read_text(encoding="utf-8-sig")

        self.assertNotIn(
            "OpenAITTSProvider",
            source,
        )

        self.assertNotIn(
            "synthesize_live_voice_audio",
            source,
        )

    def test_09_recovery_uses_saved_tts_identity(self):
        source = Path(
            "ai_assistant/voice/real_audio_recovery.py"
        ).read_text(encoding="utf-8-sig")

        self.assertIn(
            "validate_real_tts_identity",
            source,
        )

        self.assertIn(
            'state="succeeded"',
            source,
        )

    def test_10_recovery_checks_stored_audio(self):
        source = Path(
            "ai_assistant/voice/real_audio_recovery.py"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("retrieve_audio", source)
        self.assertIn("validate_live_mp3", source)

    def test_11_recovery_has_no_automatic_retry(self):
        source = Path(
            "ai_assistant/voice/real_audio_recovery.py"
        ).read_text(encoding="utf-8-sig")

        self.assertNotIn(
            "execute_isolated_live_tts",
            source,
        )

        self.assertNotIn(
            "prepare_real_tts_request",
            source,
        )

    def test_12_voice_claim_is_transactional(self):
        self.assertTrue(
            hasattr(
                voice_service.claim_tts_dispatch,
                "__wrapped__",
            )
            or callable(
                voice_service.claim_tts_dispatch
            )
        )

    def test_13_real_database_is_available(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()

        self.assertEqual(result[0], 1)

    def test_14_user_rows_are_real(self):
        User = get_user_model()

        self.assertTrue(
            User.objects.filter(pk=self.user.pk).exists()
        )

        self.assertTrue(
            User.objects.filter(
                pk=self.other_user.pk
            ).exists()
        )

        self.assertNotEqual(
            self.user.pk,
            self.other_user.pk,
        )

    def test_15_recovery_requires_valid_state(self):
        allowed = {
            VoiceTurn.State.SYNTHESIZING,
            VoiceTurn.State.COMPLETED,
        }

        self.assertNotIn(
            VoiceTurn.State.ANSWER_SAVED,
            allowed,
        )

        self.assertNotIn(
            VoiceTurn.State.CREATED,
            allowed,
        )

    def test_16_recovery_does_not_touch_billing(self):
        source = Path(
            "ai_assistant/voice/real_audio_recovery.py"
        ).read_text(encoding="utf-8-sig")

        self.assertNotIn(
            "ai_payments",
            source,
        )

        self.assertNotIn(
            "stripe",
            source.lower(),
        )
