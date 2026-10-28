"""U6.3 offline reservation finalization tests."""

from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from .live_quota_models import LiveVoiceMonthlyUsage
from .live_quota_service import (
    LiveVoiceQuotaConflict,
    commit_free_voice,
    release_free_voice,
    reserve_free_voice,
)


class LiveQuotaFinalizationTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="u63_finalize_owner",
            password="local-test-only-password",
        )
        self.other = User.objects.create_user(
            username="u63_finalize_other",
            password="local-test-only-password",
        )

    def reserve(self, duration_ms=10000):
        request_id = uuid4()
        reserve_free_voice(
            user=self.user,
            request_id=request_id,
            duration_ms=duration_ms,
        )
        return request_id

    def usage(self):
        usage = LiveVoiceMonthlyUsage.objects.get(user=self.user)
        usage.refresh_from_db()
        return usage

    def test_commit_moves_reserved_to_used(self):
        request_id = self.reserve()
        result = commit_free_voice(
            user=self.user, request_id=request_id
        )
        self.assertEqual(result.state, "committed")
        self.assertEqual(self.usage().used_ms, 10000)
        self.assertEqual(self.usage().reserved_ms, 0)

    def test_duplicate_commit_does_not_double_charge(self):
        request_id = self.reserve()
        commit_free_voice(user=self.user, request_id=request_id)
        commit_free_voice(user=self.user, request_id=request_id)
        self.assertEqual(self.usage().used_ms, 10000)

    def test_release_returns_reserved_minutes(self):
        request_id = self.reserve()
        result = release_free_voice(
            user=self.user, request_id=request_id
        )
        self.assertEqual(result.state, "released")
        self.assertEqual(self.usage().used_ms, 0)
        self.assertEqual(self.usage().reserved_ms, 0)

    def test_duplicate_release_does_not_double_refund(self):
        request_id = self.reserve()
        release_free_voice(user=self.user, request_id=request_id)
        release_free_voice(user=self.user, request_id=request_id)
        self.assertEqual(self.usage().reserved_ms, 0)

    def test_commit_after_release_denied(self):
        request_id = self.reserve()
        release_free_voice(user=self.user, request_id=request_id)
        with self.assertRaises(LiveVoiceQuotaConflict):
            commit_free_voice(user=self.user, request_id=request_id)

    def test_release_after_commit_denied(self):
        request_id = self.reserve()
        commit_free_voice(user=self.user, request_id=request_id)
        with self.assertRaises(LiveVoiceQuotaConflict):
            release_free_voice(user=self.user, request_id=request_id)

    def test_other_user_cannot_finalize(self):
        request_id = self.reserve()
        with self.assertRaises(LiveVoiceQuotaConflict):
            commit_free_voice(user=self.other, request_id=request_id)
        self.assertEqual(self.usage().reserved_ms, 10000)

    def test_unknown_reservation_denied(self):
        with self.assertRaises(LiveVoiceQuotaConflict):
            commit_free_voice(
                user=self.user,
                request_id=uuid4(),
            )

    def test_finalized_request_cannot_be_reserved_again(self):
        request_id = self.reserve()
        commit_free_voice(user=self.user, request_id=request_id)
        with self.assertRaises(LiveVoiceQuotaConflict):
            reserve_free_voice(
                user=self.user,
                request_id=request_id,
                duration_ms=10000,
            )
