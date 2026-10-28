"""U6.3 partial Live Voice charging tests."""

from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from .live_quota_models import LiveVoiceMonthlyUsage
from .live_quota_service import (
    LiveVoiceQuotaConflict,
    commit_free_voice,
    reserve_free_voice,
)


class PartialLiveVoiceChargeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="u63_partial_charge",
            password="local-test-only-password",
        )

    def reserve(self, duration_ms=60000):
        request_id = uuid4()
        reserve_free_voice(
            user=self.user,
            request_id=request_id,
            duration_ms=duration_ms,
        )
        return request_id

    def usage(self):
        return LiveVoiceMonthlyUsage.objects.get(user=self.user)

    def test_charge_only_consumed_time(self):
        request_id = self.reserve()
        commit_free_voice(
            user=self.user,
            request_id=request_id,
            consumed_ms=23000,
        )
        usage = self.usage()
        self.assertEqual(usage.used_ms, 23000)
        self.assertEqual(usage.reserved_ms, 0)

    def test_zero_consumption(self):
        request_id = self.reserve()
        commit_free_voice(
            user=self.user,
            request_id=request_id,
            consumed_ms=0,
        )
        self.assertEqual(self.usage().used_ms, 0)
        self.assertEqual(self.usage().reserved_ms, 0)

    def test_cannot_charge_more_than_reserved(self):
        request_id = self.reserve()
        with self.assertRaises(LiveVoiceQuotaConflict):
            commit_free_voice(
                user=self.user,
                request_id=request_id,
                consumed_ms=60001,
            )

    def test_negative_consumption_denied(self):
        request_id = self.reserve()
        with self.assertRaises(LiveVoiceQuotaConflict):
            commit_free_voice(
                user=self.user,
                request_id=request_id,
                consumed_ms=-1,
            )

    def test_duplicate_commit_does_not_charge_twice(self):
        request_id = self.reserve()
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
        self.assertEqual(self.usage().used_ms, 23000)
