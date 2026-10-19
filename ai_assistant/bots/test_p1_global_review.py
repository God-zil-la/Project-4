from unittest.mock import patch
from django.test import TestCase
from django.contrib.auth import get_user_model
from ai_assistant.bots.models import Bot
from ai_assistant.bots.knowledge_utils import check_message_domain
import openai


class GlobalP1CategoryReviewTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="p1_global_test",
            password="test-password"
        )
        self.bot = Bot.objects.create(
            owner=self.user,
            name="Global P1 Test",
            category="business"
        )

    @staticmethod
    def response(content):
        return openai.util.convert_to_openai_object({
            "choices": [{"message": {"content": content}}],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 2,
                "total_tokens": 12
            },
            "model": "gpt-4o-mini"
        })

    @patch("ai_assistant.bots.knowledge_utils.openai.ChatCompletion.create")
    def test_every_category_reviews_ambiguous_first_message(self, api):
        message = (
            "Kan du göra en arbetsbok till mig och "
            "göra ett nedladdningsbart dokument?"
        )

        for category, _ in Bot.CATEGORY_CHOICES:
            if category == "general":
                continue

            with self.subTest(category=category):
                self.bot.category = category
                api.reset_mock()
                api.side_effect = [
                    self.response("OUT_OF_DOMAIN|Unrelated."),
                    self.response("CONTINUE")
                ]

                result = check_message_domain(self.bot, message)

                self.assertTrue(result["in_domain"])
                self.assertEqual(api.call_count, 2)
                self.assertEqual(result["tokens_used"], 24)

    @patch("ai_assistant.bots.knowledge_utils.openai.ChatCompletion.create")
    def test_every_category_still_rejects_unrelated_requests(self, api):
        for category, _ in Bot.CATEGORY_CHOICES:
            if category == "general":
                continue

            with self.subTest(category=category):
                self.bot.category = category
                api.reset_mock()
                api.side_effect = [
                    self.response("OUT_OF_DOMAIN|Unrelated."),
                    self.response("SWITCH")
                ]

                result = check_message_domain(
                    self.bot,
                    "A completely unrelated standalone request"
                )

                self.assertFalse(result["in_domain"])
                self.assertEqual(api.call_count, 2)
                self.assertEqual(result["tokens_used"], 24)

    @patch("ai_assistant.bots.knowledge_utils.openai.ChatCompletion.create")
    def test_every_category_can_request_clarification(self, api):
        message = "Kan du hjälpa mig med det här?"

        for category, _ in Bot.CATEGORY_CHOICES:
            if category == "general":
                continue

            with self.subTest(category=category):
                self.bot.category = category
                api.reset_mock()
                api.side_effect = [
                    self.response("OUT_OF_DOMAIN|Unrelated."),
                    self.response("CLARIFY"),
                ]

                result = check_message_domain(self.bot, message)

                self.assertTrue(result["in_domain"])
                self.assertTrue(result["needs_clarification"])
                self.assertEqual(api.call_count, 2)
                self.assertEqual(result["tokens_used"], 24)
                self.assertEqual(result["input_tokens"], 20)
                self.assertEqual(result["output_tokens"], 4)
