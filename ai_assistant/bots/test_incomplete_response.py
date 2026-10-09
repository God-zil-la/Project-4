"""Offline regression coverage for truncated answers in the shared chat pipeline."""
from unittest.mock import patch

import openai
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from .chat_service import INCOMPLETE_RESPONSE_NOTICE, process_bot_message
from .knowledge_utils import strip_source_list
from .models import Bot, ChatMessage
from ai_assistant.dashboard.models import BotUsageLog


def completion(text, reason="stop", usage=None):
    return openai.util.convert_to_openai_object({
        "choices": [{"message": {"content": text}, "finish_reason": reason}],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        "model": "gpt-4o-mini",
    })


@patch.dict("os.environ", {"OPENAI_API_KEY": "test-only"})
class IncompleteResponseTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="incomplete")
        self.bot = Bot.objects.create(owner=self.user, name="Incomplete", category="general")
        self.api = self.enterContext(patch(
            "ai_assistant.bots.chat_service.openai.ChatCompletion.create"
        ))
        self.search = self.enterContext(patch(
            "ai_assistant.bots.chat_service.search_relevant_chunks",
            return_value={"chunks": [], "sources": [], "tokens_used": 0,
                          "input_tokens": 0, "output_tokens": 0, "model": None},
        ))

    def run_chat(self, text, notice, message="Explain this", language="auto"):
        cache.clear()
        self.bot.default_language = language
        self.api.reset_mock()
        self.api.side_effect = [completion(text, "length"), completion(notice)]
        return process_bot_message(self.user, self.bot, message)

    def test_multilingual_notice_uses_actual_answer_despite_default_or_request_language(self):
        cases = [
            ("sv", "Explain this", "Här är förklaringen", "Svaret är ofullständigt. Be assistenten fortsätta."),
            ("sv", "Answer in English", "Here is the explanation", INCOMPLETE_RESPONSE_NOTICE),
            ("auto", "Förklara detta", "Här är förklaringen", "Svaret är ofullständigt. Be assistenten fortsätta."),
            ("auto", "اشرح ذلك", "إليك الشرح", "الإجابة غير مكتملة. اطلب من المساعد المتابعة."),
            ("auto", "توضیح بده", "توضیح بیشتر", "پاسخ ناقص است. می\u200cتوانید از دستیار بخواهید ادامه دهد."),
            ("en", "日本語で説明してください", "説明はこちらです", "回答は未完了です。続けるよう依頼してください。"),
        ]
        for language, message, text, notice in cases:
            with self.subTest(language=language, message=message):
                result = self.run_chat(text, notice, message, language)
                self.assertEqual(result["response"], text + "\n\n[" + notice + "]")
                self.assertEqual(ChatMessage.objects.filter(sender="assistant").latest("pk").message,
                                 result["response"])
                self.assertEqual(self.api.call_count, 2)
                translation = self.api.call_args.kwargs
                self.assertEqual(translation["messages"][1]["content"], text)
                self.assertEqual(translation["request_timeout"], 5)

    def test_translation_usage_is_logged_without_an_extra_message_reservation(self):
        result = self.run_chat("Partial answer", INCOMPLETE_RESPONSE_NOTICE)
        self.assertEqual((result["tokens_used"], result["input_tokens"], result["output_tokens"]),
                         (30, 20, 10))
        self.assertEqual(BotUsageLog.objects.count(), 2)
        self.assertEqual(sum(BotUsageLog.objects.values_list("tokens_used", flat=True)), 30)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.monthly_message_count, 1)
        self.assertEqual(ChatMessage.objects.count(), 2)

    def test_translation_failure_preserves_answer_and_quota(self):
        self.api.side_effect = [completion("Partial answer", "length"),
                               openai.error.Timeout("private upstream details")]
        with self.assertLogs("ai_assistant.bots.chat_service", level="WARNING") as logs:
            result = process_bot_message(self.user, self.bot, "Explain")
        self.assertEqual(result["response"], "Partial answer\n\n[" + INCOMPLETE_RESPONSE_NOTICE + "]")
        self.assertNotIn("private upstream details", " ".join(logs.output))
        self.assertEqual(result["tokens_used"], 15)
        self.assertEqual(BotUsageLog.objects.count(), 1)
        self.assertEqual(result["monthly_messages_used"], 1)
        self.assertEqual(ChatMessage.objects.count(), 2)

    def test_invalid_or_truncated_translation_falls_back_but_counts_usage(self):
        invalid = [None, "", "x" * 401, "<script>alert()</script>", "[link](https://example.com)",
                   "two\nlines", "\u202etext", "..."]
        for notice in invalid:
            with self.subTest(notice=notice):
                result = self.run_chat("Partial", notice)
                self.assertTrue(result["response"].endswith("[" + INCOMPLETE_RESPONSE_NOTICE + "]"))
                self.assertEqual(result["tokens_used"], 30)
        cache.clear()
        self.api.side_effect = [completion("Partial", "length"), completion("Unfinished notice", "length")]
        result = process_bot_message(self.user, self.bot, "Explain")
        self.assertTrue(result["response"].endswith("[" + INCOMPLETE_RESPONSE_NOTICE + "]"))
        self.assertEqual(result["tokens_used"], 30)

    def test_non_length_finish_reasons_do_not_translate(self):
        for reason in ("stop", "content_filter", None):
            with self.subTest(reason=reason):
                cache.clear()
                self.api.reset_mock()
                self.api.side_effect = None
                self.api.return_value = completion("An answer", reason)
                result = process_bot_message(self.user, self.bot, "Explain")
                self.assertEqual(result["response"], "An answer")
                self.assertEqual(result["tokens_used"], 15)
                self.api.assert_called_once()

    def test_source_cleanup_preserves_notice_and_only_verified_sources(self):
        self.search.return_value.update(
            sources=[{"name": "Handbook.pdf", "knowledge_id": 7}], source_heading="Sources used"
        )
        result = self.run_chat("Partial answer\n\n**Sources used**\n- Invented (KB 99)",
                               INCOMPLETE_RESPONSE_NOTICE)
        self.assertNotIn("Invented", result["response"])
        self.assertIn("[" + INCOMPLETE_RESPONSE_NOTICE + "]", result["response"])
        self.assertTrue(result["response"].endswith("- Handbook.pdf (KB 7)"))
        self.assertNotIn("Handbook.pdf", strip_source_list(result["response"]))
        self.assertIn(INCOMPLETE_RESPONSE_NOTICE, strip_source_list(result["response"]))

    def test_translation_context_is_bounded(self):
        self.run_chat("a" * 4000, INCOMPLETE_RESPONSE_NOTICE)
        self.assertEqual(len(self.api.call_args.kwargs["messages"][1]["content"]), 2000)

    def test_long_answer_persists_all_segments_with_one_quota_reservation(self):
        parts = [" ".join([f"segment{index}"] * 500) for index in range(4)]
        self.api.side_effect = [completion(part) for part in parts]
        result = process_bot_message(self.user, self.bot, "Write 2000 words about technology")
        self.assertEqual(result["response"], "\n\n".join(parts))
        self.assertEqual((result["tokens_used"], result["input_tokens"], result["output_tokens"]),
                         (60, 40, 20))
        self.assertEqual(BotUsageLog.objects.count(), 1)
        self.assertEqual(BotUsageLog.objects.get().tokens_used, 60)
        self.assertEqual(ChatMessage.objects.count(), 2)
        self.assertEqual(ChatMessage.objects.get(sender="assistant").message, result["response"])
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.monthly_message_count, 1)

    def test_intermediate_source_footer_does_not_discard_later_segments(self):
        self.search.return_value.update(
            sources=[{"name": "Handbook.pdf", "knowledge_id": 7}], source_heading="Sources used"
        )
        parts = [" ".join([f"segment{index}"] * 500) for index in range(4)]
        self.api.side_effect = [completion(part + "\n\n**Sources used**\n- Invented (KB 99)")
                                for part in parts]
        result = process_bot_message(self.user, self.bot, "Write 2000 words about technology")
        for part in parts:
            self.assertIn(part, result["response"])
        self.assertNotIn("Invented", result["response"])
        self.assertEqual(result["response"].count("Handbook.pdf"), 1)
