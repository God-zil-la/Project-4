from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from ai_assistant.accounts.models import (
    UserProfile,
    current_month_start,
)
from ai_assistant.accounts.plan_utils import (
    get_ai_usage_status,
)


class MonthlyQuotaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="quota-test"
        )
        self.profile = self.user.profile

    @patch(
        "ai_assistant.accounts.plan_utils."
        "calculate_user_current_month_cost",
        return_value={"cost_usd": 0},
    )
    def test_free_limit_150(self, mocked_cost):
        self.profile.plan = UserProfile.PLAN_FREE
        self.profile.monthly_message_count = 149
        self.profile.save(
            update_fields=[
                "plan",
                "monthly_message_count",
            ]
        )

        status = get_ai_usage_status(self.user)

        self.assertTrue(status["allowed"])
        self.assertEqual(
            status["monthly_messages_used"],
            149,
        )
        self.assertEqual(
            status["monthly_message_limit"],
            150,
        )

        reservation = self.profile.reserve_message_slot(
            150
        )

        self.assertIsNotNone(reservation)

        status = get_ai_usage_status(self.user)

        self.assertFalse(status["allowed"])
        self.assertTrue(
            status["monthly_message_limit_reached"]
        )
        self.assertEqual(
            status["monthly_messages_used"],
            150,
        )

    @patch(
        "ai_assistant.accounts.plan_utils."
        "calculate_user_current_month_cost",
        return_value={"cost_usd": 0},
    )
    def test_premium_limit_3000(self, mocked_cost):
        self.profile.plan = UserProfile.PLAN_PREMIUM
        self.profile.monthly_message_count = 2999
        self.profile.save(
            update_fields=[
                "plan",
                "monthly_message_count",
            ]
        )

        status = get_ai_usage_status(self.user)

        self.assertTrue(status["allowed"])
        self.assertEqual(
            status["monthly_message_limit"],
            3000,
        )

        reservation = self.profile.reserve_message_slot(
            3000
        )

        self.assertIsNotNone(reservation)

        status = get_ai_usage_status(self.user)

        self.assertFalse(status["allowed"])
        self.assertEqual(
            status["monthly_messages_used"],
            3000,
        )

    @patch(
        "ai_assistant.accounts.plan_utils."
        "calculate_user_current_month_cost",
        return_value={"cost_usd": 0},
    )
    def test_pro_limit_10000(self, mocked_cost):
        self.profile.plan = UserProfile.PLAN_PRO
        self.profile.monthly_message_count = 9999
        self.profile.save(
            update_fields=[
                "plan",
                "monthly_message_count",
            ]
        )

        status = get_ai_usage_status(self.user)

        self.assertTrue(status["allowed"])
        self.assertEqual(
            status["monthly_message_limit"],
            10000,
        )

        reservation = self.profile.reserve_message_slot(
            10000
        )

        self.assertIsNotNone(reservation)

        status = get_ai_usage_status(self.user)

        self.assertFalse(status["allowed"])
        self.assertEqual(
            status["monthly_messages_used"],
            10000,
        )

    @patch(
        "ai_assistant.accounts.plan_utils."
        "calculate_user_current_month_cost",
        return_value={"cost_usd": 0},
    )
    def test_month_rollover_resets_counter(
        self,
        mocked_cost,
    ):
        current_start = current_month_start()

        previous_month_start = (
            current_start - timedelta(days=1)
        ).replace(day=1)

        UserProfile.objects.filter(
            pk=self.profile.pk
        ).update(
            monthly_message_count=150,
            message_count_period_start=previous_month_start,
        )

        status = get_ai_usage_status(self.user)

        self.profile.refresh_from_db()

        self.assertTrue(status["allowed"])
        self.assertEqual(
            self.profile.monthly_message_count,
            0,
        )
        self.assertEqual(
            self.profile.message_count_period_start,
            current_start,
        )

    @patch(
        "ai_assistant.accounts.plan_utils."
        "calculate_user_current_month_cost",
        return_value={"cost_usd": 0},
    )
    def test_plan_change_does_not_reset_counter(
        self,
        mocked_cost,
    ):
        self.profile.plan = UserProfile.PLAN_FREE
        self.profile.monthly_message_count = 100
        self.profile.save(
            update_fields=[
                "plan",
                "monthly_message_count",
            ]
        )

        self.profile.plan = UserProfile.PLAN_PREMIUM
        self.profile.save(
            update_fields=["plan"]
        )

        status = get_ai_usage_status(self.user)

        self.assertEqual(
            status["monthly_messages_used"],
            100,
        )

    @patch(
        "ai_assistant.accounts.plan_utils."
        "calculate_user_current_month_cost",
        return_value={"cost_usd": 0},
    )
    def test_quota_is_shared_across_multiple_bots(
        self,
        mocked_cost,
    ):
        from ai_assistant.bots.models import Bot

        first_bot = Bot.objects.create(
            owner=self.user,
            name="First",
        )
        second_bot = Bot.objects.create(
            owner=self.user,
            name="Second",
        )

        self.profile.plan = UserProfile.PLAN_FREE
        self.profile.monthly_message_count = 149
        self.profile.save(
            update_fields=[
                "plan",
                "monthly_message_count",
            ]
        )

        status = get_ai_usage_status(self.user)

        self.assertTrue(status["allowed"])
        self.assertEqual(
            status["monthly_messages_used"],
            149,
        )

        reservation = self.profile.reserve_message_slot(
            150
        )

        self.assertIsNotNone(reservation)

        status = get_ai_usage_status(self.user)

        self.assertFalse(status["allowed"])
        self.assertEqual(
            status["monthly_messages_used"],
            150,
        )

        self.assertEqual(
            first_bot.owner_id,
            self.user.id,
        )
        self.assertEqual(
            second_bot.owner_id,
            self.user.id,
        )

    def test_only_one_final_slot_can_be_reserved(self):
        self.profile.plan = UserProfile.PLAN_FREE
        self.profile.monthly_message_count = 149
        self.profile.save(
            update_fields=[
                "plan",
                "monthly_message_count",
            ]
        )

        first = UserProfile.objects.get(
            pk=self.profile.pk
        )
        second = UserProfile.objects.get(
            pk=self.profile.pk
        )

        first_reservation = first.reserve_message_slot(
            150
        )

        second_reservation = second.reserve_message_slot(
            150
        )

        self.assertIsNotNone(
            first_reservation
        )
        self.assertIsNone(
            second_reservation
        )

        self.profile.refresh_from_db()

        self.assertEqual(
            self.profile.monthly_message_count,
            150,
        )

    def test_releasing_reserved_slot_restores_counter(self):
        self.profile.monthly_message_count = 149
        self.profile.save(
            update_fields=[
                "monthly_message_count",
            ]
        )

        reservation = self.profile.reserve_message_slot(
            150
        )

        self.assertIsNotNone(reservation)

        self.profile.refresh_from_db()

        self.assertEqual(
            self.profile.monthly_message_count,
            150,
        )

        self.profile.release_message_slot(
            reservation
        )

        self.profile.refresh_from_db()

        self.assertEqual(
            self.profile.monthly_message_count,
            149,
        )

    def test_stale_period_release_does_not_decrement_new_month(self):
        current_start = current_month_start()

        previous_month_start = (
            current_start - timedelta(days=1)
        ).replace(day=1)

        self.profile.monthly_message_count = 5
        self.profile.message_count_period_start = (
            current_start
        )
        self.profile.save(
            update_fields=[
                "monthly_message_count",
                "message_count_period_start",
            ]
        )

        self.profile.release_message_slot(
            previous_month_start
        )

        self.profile.refresh_from_db()

        self.assertEqual(
            self.profile.monthly_message_count,
            5,
        )
        self.assertEqual(
            self.profile.message_count_period_start,
            current_start,
        )