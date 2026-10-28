from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from .live_quota_models import (
    LiveVoiceMonthlyUsage,
    LiveVoiceQuotaReservation,
)
from .live_quota_service import (
    LiveVoiceQuotaConflict,
    commit_free_voice,
    release_free_voice,
    reserve_free_voice,
)


class LiveQuotaIntegrityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="u63_integrity_user",
            password="local-test-password",
        )

    def test_partial_charge_is_persisted(self):
        request_id = uuid4()
        reserve_free_voice(
            user=self.user,
            request_id=request_id,
            duration_ms=60000,
        )
        commit_free_voice(
            user=self.user,
            request_id=request_id,
            consumed_ms=23000,
        )

        reservation = LiveVoiceQuotaReservation.objects.get(
            request_id=request_id
        )
        usage = LiveVoiceMonthlyUsage.objects.get(user=self.user)

        self.assertEqual(reservation.charged_ms, 23000)
        self.assertEqual(usage.used_ms, 23000)
        self.assertEqual(usage.reserved_ms, 0)

    def test_same_charge_retry_is_idempotent(self):
        request_id = uuid4()
        reserve_free_voice(
            user=self.user,
            request_id=request_id,
            duration_ms=60000,
        )
        commit_free_voice(
            user=self.user,
            request_id=request_id,
            consumed_ms=23000,
        )
        commit_free_voice(
            user=self.user,
            request_id=request_id,
            consumed_ms=23000,
        )

        usage = LiveVoiceMonthlyUsage.objects.get(user=self.user)
        self.assertEqual(usage.used_ms, 23000)

    def test_different_charge_retry_is_rejected(self):
        request_id = uuid4()
        reserve_free_voice(
            user=self.user,
            request_id=request_id,
            duration_ms=60000,
        )
        commit_free_voice(
            user=self.user,
            request_id=request_id,
            consumed_ms=23000,
        )

        with self.assertRaises(LiveVoiceQuotaConflict):
            commit_free_voice(
                user=self.user,
                request_id=request_id,
                consumed_ms=45000,
            )

    def test_release_does_not_charge(self):
        request_id = uuid4()
        reserve_free_voice(
            user=self.user,
            request_id=request_id,
            duration_ms=60000,
        )
        release_free_voice(
            user=self.user,
            request_id=request_id,
        )

        usage = LiveVoiceMonthlyUsage.objects.get(user=self.user)
        self.assertEqual(usage.used_ms, 0)
        self.assertEqual(usage.reserved_ms, 0)

    def test_reservation_binds_to_user(self):
        request_id = uuid4()
        reservation = reserve_free_voice(
            user=self.user,
            request_id=request_id,
            duration_ms=60000,
        )
        self.assertEqual(reservation.user_id, self.user.pk)