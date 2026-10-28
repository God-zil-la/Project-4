"""Regression tests for the disabled U6.3 STT provider dispatch."""

from unittest.mock import patch

from django.test import SimpleTestCase

from ai_assistant.voice.service import VoiceConflict
from ai_assistant.voice.stt_runner import execute_reserved_stt


class STTDispatchGuardTests(SimpleTestCase):
    def test_provider_dispatch_remains_disabled(self):
        with patch(
            "ai_assistant.voice.stt_runner.prepare_reserved_stt",
            return_value=(object(), object()),
        ) as prepare:
            with self.assertRaisesRegex(
                VoiceConflict,
                "STT provider dispatch is not enabled yet",
            ):
                execute_reserved_stt(
                    user=object(),
                    session_id="test-session",
                    request_id="test-request",
                    reservation=object(),
                    evidence=object(),
                    audio=object(),
                    api_key="test-only-key",
                )

        prepare.assert_called_once()

    def test_failed_preparation_blocks_dispatch(self):
        with patch(
            "ai_assistant.voice.stt_runner.prepare_reserved_stt",
            side_effect=VoiceConflict("Invalid reservation"),
        ) as prepare:
            with self.assertRaisesRegex(
                VoiceConflict,
                "Invalid reservation",
            ):
                execute_reserved_stt(
                    user=object(),
                    session_id="test-session",
                    request_id="test-request",
                    reservation=object(),
                    evidence=object(),
                    audio=object(),
                    api_key="test-only-key",
                )

        prepare.assert_called_once()
