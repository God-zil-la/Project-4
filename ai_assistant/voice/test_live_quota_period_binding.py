"""U6.3 reservation identity across monthly periods."""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from .live_quota_service import (
    LiveVoiceQuotaConflict,
    reserve_free_voice,
)


class LiveQuotaPeriodBindingTests(TestCase):
    def test_request_cannot_be_reused_next_month(self):
        user = get_user_model().objects.create_user(
            username="u63_period_binding",
            password="local-test-only-password",
        )
        request_id = uuid4()

        october = datetime(
            2026, 10, 31, 23, 59, tzinfo=timezone.utc
        )
        november = datetime(
            2026, 11, 1, 0, 1, tzinfo=timezone.utc
        )

        with patch(
            "ai_assistant.voice.live_quota_service.timezone.now",
            return_value=october,
        ):
            reserve_free_voice(
                user=user,
                request_id=request_id,
                duration_ms=1000,
            )

        with patch(
            "ai_assistant.voice.live_quota_service.timezone.now",
            return_value=november,
        ):
            with self.assertRaises(LiveVoiceQuotaConflict):
                reserve_free_voice(
                    user=user,
                    request_id=request_id,
                    duration_ms=1000,
                )
