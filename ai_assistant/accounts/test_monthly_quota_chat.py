from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from ai_assistant.accounts.models import UserProfile
from ai_assistant.bots.chat_service import (
    ChatUsageLimitError,
    process_bot_message,
)
from ai_assistant.bots.models import (
    Bot,
    ChatMessage,
)


class MonthlyQuotaChatTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="quota-chat-test"
        )

        self.bot = Bot.objects.create(
            owner=self.user,
            name="Quota Bot",
            category="general",
        )

        self.profile = self.user.profile

    @patch(
        "ai_assistant.accounts.plan_utils."
        "calculate_user_current_month_cost",
        return_value={"cost_usd": 0},
    )
    @patch(
        "ai_assistant.bots.chat_service."
        "openai.ChatCompletion.create"
    )
    def test_chat_is_blocked_at_monthly_limit(
        self,
        openai_create,
        mocked_cost,
    ):
        self.profile.plan = UserProfile.PLAN_FREE
        self.profile.monthly_message_count = 150
        self.profile.save(
            update_fields=[
                "plan",
                "monthly_message_count",
            ]
        )

        with self.assertRaises(
            ChatUsageLimitError
        ) as error:
            process_bot_message(
                self.user,
                self.bot,
                "This message must not reach AI.",
            )

        self.assertEqual(
            str(error.exception),
            "Monthly AI message limit reached.",
        )

        openai_create.assert_not_called()

        self.assertEqual(
            ChatMessage.objects.count(),
            0,
        )

        self.profile.refresh_from_db()

        self.assertEqual(
            self.profile.monthly_message_count,
            150,
        )