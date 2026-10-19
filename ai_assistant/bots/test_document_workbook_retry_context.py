import copy
import json
from unittest import TestCase
from unittest.mock import patch

from .test_document_export_regressions import REQUEST, budget_spec
from .document_workbook import generate_workbook_spec


class WorkbookRetryContextTests(TestCase):

    @patch("ai_assistant.bots.document_workbook.provider_call")
    def test_retry_receives_invalid_spec_and_precise_error(self, provider):
        invalid = copy.deepcopy(budget_spec())
        invalid["sheets"][0]["rows"][1][1] = "MISSING"

        valid = budget_spec()

        provider.side_effect = [
            {
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(invalid)},
                }]
            },
            {
                "choices": [{
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(valid)},
                }]
            },
        ]

        generate_workbook_spec(REQUEST, [])

        self.assertEqual(provider.call_count, 2)

        retry_messages = provider.call_args.kwargs["messages"]

        self.assertTrue(any(
            message["role"] == "assistant"
            and message["content"] == json.dumps(invalid)
            for message in retry_messages
        ))

        self.assertTrue(any(
            "Missing source input: amount_1" in message["content"]
            for message in retry_messages
        ))
