"""U6.3 offline quota reservation tests."""

from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from .live_quota_models import (
    LiveVoiceMonthlyUsage,
    LiveVoiceQuotaReservation,
)
from .live_quota_service import (
    LiveVoiceQuotaExceeded,
    LiveVoiceQuotaConflict,
    reserve_free_voice,
)


class FreeLiveQuotaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="u63_quota_test",
            password="local-test-only-password",
        )

    def reserve(self, duration_ms, request_id=None):
        return reserve_free_voice(
            user=self.user,
            request_id=request_id or uuid4(),
            duration_ms=duration_ms,
        )

    def test_first_reservation(self):
        reservation = self.reserve(1000)
        self.assertEqual(reservation.duration_ms, 1000)
        self.assertEqual(reservation.state, "reserved")

        usage = reservation.usage
        usage.refresh_from_db()
        self.assertEqual(usage.reserved_ms, 1000)
        self.assertEqual(usage.used_ms, 0)

    def test_exact_ten_minutes(self):
        self.reserve(600_000)

        with self.assertRaises(LiveVoiceQuotaExceeded):
            self.reserve(1)

    def test_exceed_limit_denied(self):
        with self.assertRaises(LiveVoiceQuotaExceeded):
            self.reserve(600_001)

    def test_idempotent_request(self):
        request_id = uuid4()
        first = self.reserve(2000, request_id)
        second = self.reserve(2000, request_id)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            LiveVoiceQuotaReservation.objects.count(), 1
        )

    def test_conflicting_retry_denied(self):
        request_id = uuid4()
        self.reserve(2000, request_id)

        with self.assertRaises(LiveVoiceQuotaConflict):
            self.reserve(3000, request_id)

    def test_invalid_duration_denied(self):
        for duration in (0, -1, 1.5, True):
            with self.subTest(duration=duration):
                with self.assertRaises(LiveVoiceQuotaConflict):
                    self.reserve(duration)

    def test_invalid_request_id_denied(self):
        with self.assertRaises(LiveVoiceQuotaConflict):
            reserve_free_voice(
                user=self.user,
                request_id="invalid-uuid",
                duration_ms=1000,
            )

    def test_usage_never_exceeds_limit(self):
        self.reserve(400_000)
        self.reserve(200_000)

        usage = LiveVoiceMonthlyUsage.objects.get(user=self.user)
        self.assertEqual(
            usage.used_ms + usage.reserved_ms,
            600_000,
        )
