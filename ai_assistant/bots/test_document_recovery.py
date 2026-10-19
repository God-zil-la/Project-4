"""Regression checks for a single safe retry of document content."""

from unittest.mock import patch

from django.test import SimpleTestCase

from .document_ai_intent import regenerate_document_content


class DocumentContentRecoveryTests(SimpleTestCase):
    def setUp(self):
        self.history = [
            {"role": "system", "content": "Respond in Swedish. Remain in scope."},
            {"role": "user", "content": "Make a PDF about cycling."},
        ]

    @patch("ai_assistant.bots.document_ai_intent.provider_call")
    def test_pdf_recovery_preserves_scope_and_accounts_tokens(self, provider):
        provider.return_value = {
            "choices": [{"finish_reason": "stop", "message": {
                "content": "# Cycling\n\n## Maintenance\nCheck the brakes."
            }}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
            "model": "gpt-4o-mini",
        }
        draft, usage = regenerate_document_content(
            message="Create my PDF now", openai_messages=self.history,
            file_format="pdf", model="gpt-4o-mini",
        )
        self.assertIn("Maintenance", draft)
        self.assertEqual(usage["tokens_used"], 30)
        messages = provider.call_args.kwargs["messages"]
        self.assertIn(self.history[0], messages)
        self.assertIn(self.history[1], messages)
        self.assertIn("PDF", messages[-1]["content"])
        self.assertEqual(provider.call_count, 1)

    @patch("ai_assistant.bots.document_ai_intent.provider_call")
    def test_csv_retry_requires_complete_provider_response(self, provider):
        provider.return_value = {
            "choices": [{"finish_reason": "length", "message": {
                "content": "product,price\nCoffee,25"
            }}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 6},
        }
        draft, usage = regenerate_document_content(
            message="Create CSV", openai_messages=self.history,
            file_format="csv", model="gpt-4o-mini",
        )
        self.assertIsNone(draft)
        self.assertEqual(usage["tokens_used"], 11)
        self.assertIn("CSV table", provider.call_args.kwargs["messages"][-1]["content"])

    @patch("ai_assistant.bots.document_ai_intent.provider_call")
    def test_xlsx_cannot_use_prose_recovery(self, provider):
        with self.assertRaises(ValueError):
            regenerate_document_content(
                message="Create XLSX", openai_messages=self.history,
                file_format="xlsx", model="gpt-4o-mini",
            )
        provider.assert_not_called()
