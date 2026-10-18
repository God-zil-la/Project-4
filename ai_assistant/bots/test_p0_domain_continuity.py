
from unittest.mock import patch

import openai
from django.test import TestCase

from ai_assistant.bots.knowledge_utils import check_message_domain
from ai_assistant.bots.models import Bot


class DomainContinuityRegressionTests(TestCase):

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"})
    @patch(
        "ai_assistant.bots.knowledge_utils."
        "openai.ChatCompletion.create"
    )
    def test_assistant_offer_followup_must_not_be_rejected(self, api):
        response = openai.util.convert_to_openai_object({
            "choices": [{
                "message": {
                    "content": (
                        "OUT_OF_DOMAIN|Please ask a related question."
                    )
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18,
            },
            "model": "gpt-4o-mini",
        })
        review = openai.util.convert_to_openai_object({
            "choices": [{"message": {"content": "CONTINUE"}}],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 1,
                "total_tokens": 13,
            },
            "model": "gpt-4o-mini",
        })
        api.side_effect = [response, review]

        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            username="domain_continuity_test",
            password="test-password",
        )
        bot = Bot.objects.create(
            owner=user,
            name="Fitness Test Assistant",
            category="fitness",
        )

        result = check_message_domain(
            bot,
            "Ja g?rna, g?r en s?dan spellista",
            conversation_context=(
                "USER: I am planning my workouts.\n"
                "ASSISTANT: Would you like a workout playlist?"
            ),
        )

        self.assertTrue(
            result["in_domain"],
            "A legitimate reply to an in-domain assistant offer "
            "must not be rejected solely by the first classifier."
        )


    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"})
    @patch(
        "ai_assistant.bots.knowledge_utils."
        "openai.ChatCompletion.create"
    )
    def test_p0_rejects_real_topic_switch(self, api):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="p0_switch",
            password="test-password",
        )
        bot = Bot.objects.create(
            owner=user,
            name="Fitness Assistant",
            category="fitness",
        )

        def completion(content, prompt, output):
            return openai.util.convert_to_openai_object({
                "choices": [{"message": {"content": content}}],
                "usage": {
                    "prompt_tokens": prompt,
                    "completion_tokens": output,
                    "total_tokens": prompt + output,
                },
                "model": "gpt-4o-mini",
            })

        api.side_effect = [
            completion("OUT_OF_DOMAIN|Please ask about fitness.", 10, 8),
            completion("SWITCH", 12, 1),
        ]

        result = check_message_domain(
            bot,
            "Write a Python web scraper unrelated to training.",
            conversation_context=(
                "USER: I am planning my workouts.\\n"
                "ASSISTANT: Would you like a workout playlist?"
            ),
        )

        self.assertFalse(result["in_domain"])
        self.assertEqual(
            result["rejection_message"],
            "Please ask about fitness.",
        )
        self.assertEqual(result["tokens_used"], 31)
        self.assertEqual(result["input_tokens"], 22)
        self.assertEqual(result["output_tokens"], 9)
        self.assertEqual(api.call_count, 2)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"})
    @patch(
        "ai_assistant.bots.knowledge_utils."
        "openai.ChatCompletion.create"
    )
    def test_p0_continuation_counts_both_calls(self, api):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="p0_accounting",
            password="test-password",
        )
        bot = Bot.objects.create(
            owner=user,
            name="Fitness Assistant",
            category="fitness",
        )

        def completion(content, prompt, output):
            return openai.util.convert_to_openai_object({
                "choices": [{"message": {"content": content}}],
                "usage": {
                    "prompt_tokens": prompt,
                    "completion_tokens": output,
                    "total_tokens": prompt + output,
                },
                "model": "gpt-4o-mini",
            })

        api.side_effect = [
            completion("OUT_OF_DOMAIN|Please ask about fitness.", 10, 8),
            completion("CONTINUE", 12, 1),
        ]

        result = check_message_domain(
            bot,
            "Ja g?rna, g?r en s?dan spellista.",
            conversation_context=(
                "USER: I am planning my workouts.\\n"
                "ASSISTANT: Would you like a workout playlist?"
            ),
        )

        self.assertTrue(result["in_domain"])
        self.assertEqual(result["rejection_message"], "")
        self.assertEqual(result["tokens_used"], 31)
        self.assertEqual(result["input_tokens"], 22)
        self.assertEqual(result["output_tokens"], 9)
        self.assertEqual(api.call_count, 2)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"})
    @patch(
        "ai_assistant.bots.knowledge_utils."
        "openai.ChatCompletion.create"
    )
    def test_p0_invalid_review_does_not_approve(self, api):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="p0_invalid",
            password="test-password",
        )
        bot = Bot.objects.create(
            owner=user,
            name="Fitness Assistant",
            category="fitness",
        )

        def completion(content):
            return openai.util.convert_to_openai_object({
                "choices": [{"message": {"content": content}}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 1,
                    "total_tokens": 11,
                },
                "model": "gpt-4o-mini",
            })

        api.side_effect = [
            completion("OUT_OF_DOMAIN|Please ask about fitness."),
            completion("UNRECOGNIZED"),
        ]

        result = check_message_domain(
            bot,
            "Write an unrelated Python web scraper.",
            conversation_context=(
                "USER: I am planning my workouts.\\n"
                "ASSISTANT: Would you like a workout playlist?"
            ),
        )

        self.assertFalse(result["in_domain"])
        self.assertEqual(
            result["rejection_message"],
            "Please ask about fitness.",
        )
        self.assertEqual(api.call_count, 2)


    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"})
    @patch(
        "ai_assistant.bots.knowledge_utils."
        "openai.ChatCompletion.create"
    )
    def test_p0_review_api_failure(self, api):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="p0_api_failure",
            password="test-password",
        )
        bot = Bot.objects.create(
            owner=user,
            name="Fitness Assistant",
            category="fitness",
        )

        first_response = openai.util.convert_to_openai_object({
            "choices": [{
                "message": {
                    "content": (
                        "OUT_OF_DOMAIN|Please ask about fitness."
                    )
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18,
            },
            "model": "gpt-4o-mini",
        })

        api.side_effect = [
            first_response,
            ConnectionError("Simulated API connection failure"),
        ]

        result = check_message_domain(
            bot,
            "Ja g?rna, g?r en s?dan spellista.",
            conversation_context=(
                "USER: I am planning my workouts.\\n"
                "ASSISTANT: Would you like a workout playlist?"
            ),
        )

        self.assertFalse(result["in_domain"])
        self.assertEqual(
            result["rejection_message"],
            "Please ask about fitness.",
        )
        self.assertEqual(result["tokens_used"], 18)
        self.assertEqual(api.call_count, 2)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"})
    @patch(
        "ai_assistant.bots.knowledge_utils."
        "openai.ChatCompletion.create"
    )
    def test_p0_review_timeout(self, api):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="p0_timeout",
            password="test-password",
        )
        bot = Bot.objects.create(
            owner=user,
            name="Fitness Assistant",
            category="fitness",
        )

        first_response = openai.util.convert_to_openai_object({
            "choices": [{
                "message": {
                    "content": (
                        "OUT_OF_DOMAIN|Please ask about fitness."
                    )
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18,
            },
            "model": "gpt-4o-mini",
        })

        api.side_effect = [
            first_response,
            TimeoutError("Simulated review timeout"),
        ]

        result = check_message_domain(
            bot,
            "Ja g?rna, g?r en s?dan spellista.",
            conversation_context=(
                "USER: I am planning my workouts.\\n"
                "ASSISTANT: Would you like a workout playlist?"
            ),
        )

        self.assertFalse(result["in_domain"])
        self.assertEqual(
            result["rejection_message"],
            "Please ask about fitness.",
        )
        self.assertEqual(result["tokens_used"], 18)
        self.assertEqual(api.call_count, 2)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"})
    @patch(
        "ai_assistant.bots.knowledge_utils."
        "openai.ChatCompletion.create"
    )
    def test_p0_openai_api_connection_error(self, api):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="p0_api_failure",
            password="test-password",
        )
        bot = Bot.objects.create(
            owner=user,
            name="Fitness Assistant",
            category="fitness",
        )

        first_response = openai.util.convert_to_openai_object({
            "choices": [{
                "message": {
                    "content": (
                        "OUT_OF_DOMAIN|Please ask about fitness."
                    )
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18,
            },
            "model": "gpt-4o-mini",
        })

        api.side_effect = [
            first_response,
            openai.error.APIConnectionError("Simulated connection failure"),
        ]

        result = check_message_domain(
            bot,
            "Ja g?rna, g?r en s?dan spellista.",
            conversation_context=(
                "USER: I am planning my workouts.\\n"
                "ASSISTANT: Would you like a workout playlist?"
            ),
        )

        self.assertFalse(result["in_domain"])
        self.assertEqual(
            result["rejection_message"],
            "Please ask about fitness.",
        )
        self.assertEqual(result["tokens_used"], 18)
        self.assertEqual(api.call_count, 2)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"})
    @patch(
        "ai_assistant.bots.knowledge_utils."
        "openai.ChatCompletion.create"
    )
    def test_p0_openai_timeout(self, api):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="p0_api_failure",
            password="test-password",
        )
        bot = Bot.objects.create(
            owner=user,
            name="Fitness Assistant",
            category="fitness",
        )

        first_response = openai.util.convert_to_openai_object({
            "choices": [{
                "message": {
                    "content": (
                        "OUT_OF_DOMAIN|Please ask about fitness."
                    )
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18,
            },
            "model": "gpt-4o-mini",
        })

        api.side_effect = [
            first_response,
            openai.error.Timeout("Simulated OpenAI timeout"),
        ]

        result = check_message_domain(
            bot,
            "Ja g?rna, g?r en s?dan spellista.",
            conversation_context=(
                "USER: I am planning my workouts.\\n"
                "ASSISTANT: Would you like a workout playlist?"
            ),
        )

        self.assertFalse(result["in_domain"])
        self.assertEqual(
            result["rejection_message"],
            "Please ask about fitness.",
        )
        self.assertEqual(result["tokens_used"], 18)
        self.assertEqual(api.call_count, 2)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"})
    @patch(
        "ai_assistant.bots.knowledge_utils."
        "openai.ChatCompletion.create"
    )
    def test_p0_openai_rate_limit(self, api):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="p0_api_failure",
            password="test-password",
        )
        bot = Bot.objects.create(
            owner=user,
            name="Fitness Assistant",
            category="fitness",
        )

        first_response = openai.util.convert_to_openai_object({
            "choices": [{
                "message": {
                    "content": (
                        "OUT_OF_DOMAIN|Please ask about fitness."
                    )
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18,
            },
            "model": "gpt-4o-mini",
        })

        api.side_effect = [
            first_response,
            openai.error.RateLimitError("Simulated rate limit"),
        ]

        result = check_message_domain(
            bot,
            "Ja g?rna, g?r en s?dan spellista.",
            conversation_context=(
                "USER: I am planning my workouts.\\n"
                "ASSISTANT: Would you like a workout playlist?"
            ),
        )

        self.assertFalse(result["in_domain"])
        self.assertEqual(
            result["rejection_message"],
            "Please ask about fitness.",
        )
        self.assertEqual(result["tokens_used"], 18)
        self.assertEqual(api.call_count, 2)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"})
    @patch(
        "ai_assistant.bots.knowledge_utils."
        "openai.ChatCompletion.create"
    )
    def test_p0_openai_service_unavailable(self, api):
        from django.contrib.auth import get_user_model

        user = get_user_model().objects.create_user(
            username="p0_api_failure",
            password="test-password",
        )
        bot = Bot.objects.create(
            owner=user,
            name="Fitness Assistant",
            category="fitness",
        )

        first_response = openai.util.convert_to_openai_object({
            "choices": [{
                "message": {
                    "content": (
                        "OUT_OF_DOMAIN|Please ask about fitness."
                    )
                }
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18,
            },
            "model": "gpt-4o-mini",
        })

        api.side_effect = [
            first_response,
            openai.error.ServiceUnavailableError("Simulated service outage"),
        ]

        result = check_message_domain(
            bot,
            "Ja g?rna, g?r en s?dan spellista.",
            conversation_context=(
                "USER: I am planning my workouts.\\n"
                "ASSISTANT: Would you like a workout playlist?"
            ),
        )

        self.assertFalse(result["in_domain"])
        self.assertEqual(
            result["rejection_message"],
            "Please ask about fitness.",
        )
        self.assertEqual(result["tokens_used"], 18)
        self.assertEqual(api.call_count, 2)
