"""U4.1 focused mocked regression tests. No live OpenAI calls or database writes."""
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from ai_assistant.bots import chat_service as service


class _Choice(dict):
    @property
    def message(self):
        return self["message"]


class _Response(dict):
    @property
    def choices(self):
        return self["choices"]


def _api_response(text, input_tokens=10, output_tokens=20, finish_reason="stop"):
    return _Response(
        model="gpt-4o-mini",
        usage={
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
        choices=[_Choice(message={"content": text}, finish_reason=finish_reason)],
    )


def _part(index, words=500):
    return " ".join([f"part{index}"] * words)


class U41LongResponseTests(SimpleTestCase):
    def setUp(self):
        self.user = MagicMock()
        self.profile = MagicMock()
        self.profile.reserve_message_slot.return_value = "period"
        self.profile.effective_plan = "pro"
        self.profile.monthly_message_count = 1
        self.user.profile = self.profile
        self.bot = SimpleNamespace(pk=298, default_language="my")
        self.conversation = SimpleNamespace(public_id="test-conversation")
        self.patches = [
            patch.object(service, "_check_rate_limit"),
            patch.object(service, "get_ai_usage_status", return_value={
                "allowed": True, "monthly_message_limit": 100,
            }),
            patch.object(service, "_resolve_conversation", return_value=self.conversation),
            patch.object(service, "_set_conversation_title"),
            patch.object(service, "_build_domain_context", return_value=""),
            patch.object(service, "check_message_domain", return_value={
                "in_domain": True, "tokens_used": 7, "input_tokens": 5,
                "output_tokens": 2, "model": "classifier-model",
            }),
            patch.object(service, "_build_retrieval_context", return_value=""),
            patch.object(service, "search_relevant_chunks", return_value={
                "chunks": [], "sources": [], "tokens_used": 11,
                "input_tokens": 11, "output_tokens": 0,
                "model": "embedding-model",
            }),
            patch.object(service, "render_system_message", return_value="Base assistant rules."),
            patch.object(service, "_build_history", side_effect=lambda conv, sys: [
                {"role": "system", "content": sys},
            ]),
            patch.object(service, "append_source_list", side_effect=lambda text, *args, **kwargs: text),
            patch.object(service, "_save_chat_exchange"),
            patch.object(service, "_log_usage"),
            patch.dict(os.environ, {"OPENAI_API_KEY": "mock-key"}),
            patch.object(service.openai.ChatCompletion, "create"),
        ]
        self.started = [p.start() for p in self.patches]
        self.addCleanup(lambda: [p.stop() for p in reversed(self.patches)])
        self.api = self.started[-1]
        self.usage_log = self.started[-3]
        self.saved = self.started[-4]

    def _run(self, responses, prompt="Skriv 2000 ord om hållbar teknik."):
        self.api.side_effect = responses
        return service.process_bot_message(self.user, self.bot, prompt)

    def test_2000_words_requests_four_parts(self):
        result = self._run([_api_response(_part(n)) for n in range(1, 5)])
        self.assertEqual(self.api.call_count, 4)
        for n in range(1, 5):
            self.assertIn(_part(n), result["response"])
        self.assertEqual(
            result["response"],
            "\n\n".join(_part(n) for n in range(1, 5)),
        )
        self.assertEqual(len(result["response"].split()), 2000)

    def test_burmese_default_language_on_every_call(self):
        self._run([_api_response(_part(n)) for n in range(4)])
        for call in self.api.call_args_list:
            messages = call.kwargs["messages"]
            self.assertIn("Burmese (Myanmar)", messages[0]["content"])
            self.assertIn("language specified", messages[-1]["content"])

    def test_continuations_include_prior_output_and_no_repeat_instruction(self):
        self._run([_api_response(_part(n)) for n in range(4)])
        for index in range(1, 4):
            messages = self.api.call_args_list[index].kwargs["messages"]
            self.assertTrue(any(
                m["role"] == "assistant" and m["content"] == _part(index - 1)
                for m in messages
            ))
            self.assertTrue(any(
                m["role"] == "user" and "do not repeat" in m["content"]
                for m in messages
            ))

    def test_usage_aggregates_all_generation_calls_and_auxiliary_usage(self):
        result = self._run([_api_response(_part(n), 10 + n, 20 + n) for n in range(4)])
        # classifier: 5/2, embeddings: 11/0, generation: 46/86
        self.assertEqual(result["input_tokens"], 62)
        self.assertEqual(result["output_tokens"], 88)
        self.assertEqual(result["tokens_used"], 150)
        generation_logs = [c.kwargs for c in self.usage_log.call_args_list
                           if c.kwargs.get("model") == "gpt-4o-mini"]
        self.assertEqual(len(generation_logs), 1)
        self.assertEqual(generation_logs[0]["tokens_used"], 132)
        self.assertEqual(self.saved.call_count, 1)

    def test_length_finish_adds_notice_and_logs_translation_usage(self):
        with patch.object(service, "_localize_incomplete_notice", return_value=(
            "Response incomplete", {"input_tokens": 3, "output_tokens": 4,
                                    "tokens_used": 7, "model": "notice-model"},
        )):
            result = self._run([_api_response("Partial text", finish_reason="length")], prompt="Explain")
        self.assertEqual(self.api.call_count, 1)
        self.assertIn("[Response incomplete]", result["response"])
        self.assertEqual(result["tokens_used"], 7 + 11 + 30 + 7)

    def test_other_finish_reasons_do_not_add_token_limit_notice(self):
        for reason in (None, "content_filter"):
            with self.subTest(reason=reason):
                self.api.reset_mock(side_effect=True)
                result = self._run([_api_response("An answer", finish_reason=reason)],
                                   prompt="Hello")
                self.assertNotIn("Response incomplete", result["response"])

    def test_length_finish_continues_and_removes_notice_after_recovery(self):
        result = self._run([
            _api_response(_part(0, 250), finish_reason="length"),
            *[_api_response(_part(n)) for n in range(1, 4)],
            _api_response(_part(4, 250)),
        ])
        self.assertEqual(self.api.call_count, 5)
        self.assertEqual(len(result["response"].split()), 2000)
        self.assertNotIn("Response incomplete", result["response"])
        self.assertEqual(result["tokens_used"], 18 + 5 * 30)

    def test_short_segments_get_extra_calls_until_target(self):
        result = self._run([_api_response(_part(n, 400)) for n in range(5)])
        self.assertEqual(self.api.call_count, 5)
        self.assertEqual(len(result["response"].split()), 2000)
        self.assertIn("approximately 400 new words", self.api.call_args.kwargs["messages"][-1]["content"])

    def test_call_limit_marks_short_or_truncated_output_and_counts_usage(self):
        for reason in ("stop", "length"):
            with self.subTest(reason=reason), patch.object(
                service, "_localize_incomplete_notice", return_value=("Incomplete", {})
            ):
                self.api.reset_mock(side_effect=True)
                result = self._run([_api_response(_part(n, 100), finish_reason=reason)
                                    for n in range(6)])
                self.assertEqual(self.api.call_count, 6)
                self.assertTrue(result["response"].endswith("[Incomplete]"))
                self.assertEqual(result["tokens_used"], 198)

    def test_large_first_part_stops_without_redundant_calls(self):
        result = self._run([_api_response(_part(0, 2000))])
        self.assertEqual(self.api.call_count, 1)
        self.assertEqual(len(result["response"].split()), 2000)

    def test_empty_repeated_and_filtered_parts_stop_without_retry(self):
        for text, reason in (("", "stop"), (_part(0), "stop"), ("Filtered", "content_filter")):
            with self.subTest(reason=reason, text=text[:10]), patch.object(
                service, "_localize_incomplete_notice", return_value=("Incomplete", {})
            ):
                self.api.reset_mock(side_effect=True)
                result = self._run([_api_response(_part(0)), _api_response(text, finish_reason=reason)])
                self.assertEqual(self.api.call_count, 2)
                self.assertEqual(result["response"].count(_part(0)), 1)
                self.assertEqual(result["tokens_used"], 78)

    def test_continuation_timeout_preserves_answer_and_quota(self):
        with patch.object(service, "_localize_incomplete_notice", return_value=("Incomplete", {})):
            result = self._run([_api_response(_part(0)), service.openai.error.Timeout("secret")])
        self.assertIn(_part(0), result["response"])
        self.assertEqual(result["tokens_used"], 48)
        self.saved.assert_called_once()
        self.profile.reserve_message_slot.assert_called_once()
        self.profile.release_message_slot.assert_not_called()

    def test_first_call_failure_releases_quota(self):
        with self.assertRaises(service.openai.error.Timeout):
            self._run([service.openai.error.Timeout("test")])
        self.profile.release_message_slot.assert_called_once_with("period")
        self.saved.assert_not_called()

    def test_auto_language_is_not_a_named_response_language(self):
        self.bot.default_language = "auto"
        self._run([_api_response("Hello")], prompt="Hello")
        self.assertNotIn("Reply in auto", self.api.call_args.kwargs["messages"][0]["content"])

    def test_word_request_formats_and_unrelated_numbers(self):
        for prompt in ("2000 words", "2,000 words", "2.000 ord", "2 000 ord"):
            self.assertEqual(service._requested_word_count(prompt), 2000)
        self.assertIsNone(service._requested_word_count("Explain the year 2000"))
