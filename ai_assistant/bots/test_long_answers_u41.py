"""U4.1 long-answer continuation regression tests."""

from unittest.mock import patch

import openai
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from .chat_service import process_bot_message, _requested_word_count
from .models import Bot, ChatMessage
from ai_assistant.dashboard.models import BotUsageLog


def completion(text, reason="stop"):
    return openai.util.convert_to_openai_object({
        "choices": [{
            "message": {"content": text},
            "finish_reason": reason,
        }],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15,
        },
        "model": "gpt-4o-mini",
    })


@patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"})
class LongAnswerU41Tests(TestCase):

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="u41_long_answer"
        )
        self.bot = Bot.objects.create(
            owner=self.user,
            name="General Long Answer",
            category="general",
        )
        self.bot.default_language = "my"

        self.api = self.enterContext(patch(
            "ai_assistant.bots.chat_service.openai.ChatCompletion.create"
        ))
        self.search = self.enterContext(patch(
            "ai_assistant.bots.chat_service.search_relevant_chunks",
            return_value={
                "chunks": [],
                "sources": [],
                "tokens_used": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "model": None,
            },
        ))

    def test_word_count_parsing(self):
        self.assertEqual(_requested_word_count("cirka 2 000 ord"), 2000)
        self.assertEqual(_requested_word_count("about 2,000 words"), 2000)
        self.assertEqual(_requested_word_count("2000 words"), 2000)
        self.assertIsNone(_requested_word_count("Explain this"))

    def test_long_answer_continues_and_counts_usage(self):
        self.api.side_effect = [
            completion("Introduction."),
            completion("Detailed explanation. " * 700),
        ]

        result = process_bot_message(
            self.user,
            self.bot,
            "Write about 2,000 words about software architecture.",
        )

        self.assertEqual(self.api.call_count, 2)
        self.assertIn("Introduction.", result["response"])
        self.assertIn("Detailed explanation.", result["response"])
        self.assertEqual(result["tokens_used"], 30)
        self.assertEqual(result["input_tokens"], 20)
        self.assertEqual(result["output_tokens"], 10)

        self.assertEqual(BotUsageLog.objects.count(), 1)
        self.assertEqual(ChatMessage.objects.count(), 2)

        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.monthly_message_count, 1)

        first = self.api.call_args_list[0].kwargs
        second = self.api.call_args_list[1].kwargs

        self.assertEqual(first["max_tokens"], 4000)
        self.assertEqual(second["max_tokens"], 4000)
        self.assertEqual(
            first["messages"][0]["content"],
            second["messages"][0]["content"],
        )

    def test_short_normal_request_does_not_continue(self):
        self.api.return_value = completion("A normal answer.")

        result = process_bot_message(
            self.user,
            self.bot,
            "Explain databases briefly.",
        )

        self.api.assert_called_once()
        self.assertEqual(result["response"], "A normal answer.")

    def test_content_filter_does_not_trigger_continuation(self):
        self.api.return_value = completion(
            "Cannot provide that content.",
            "content_filter",
        )

        result = process_bot_message(
            self.user,
            self.bot,
            "Write 2000 words about a restricted subject.",
        )

        self.api.assert_called_once()
        self.assertEqual(
            result["response"],
            "Cannot provide that content.",
        )
