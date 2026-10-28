from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from . import saved_synthesis, service


class SavedSynthesisStorageTests(SimpleTestCase):
    def test_success_uses_storage_pipeline(self):
        request_id = uuid4()
        row = type("Row", (), {
            "pk": uuid4(),
            "request_id": request_id,
            "fingerprint": "original",
        })()
        user = type("User", (), {"pk": 12})()
        store = object()

        with patch.object(saved_synthesis, "prepare_saved_response", return_value=row), \
             patch.object(service, "claim", return_value=True), \
             patch.object(saved_synthesis, "get_assistant_message", return_value="Saved answer"), \
             patch.object(saved_synthesis, "validate_saved_response",
                          return_value=(request_id, "original")), \
             patch.object(saved_synthesis.MockProvider, "synthesize",
                          return_value=b"mock-audio"), \
             patch.object(saved_synthesis, "store_synthesized_audio") as finalize, \
             patch.object(service, "finish") as finish:

            result = saved_synthesis.synthesize_saved_response(
                user=user,
                assistant_id=7,
                conversation_id=uuid4(),
                message_id=42,
                request_id=request_id,
                audio_store=store,
            )

        self.assertEqual(result.state, "succeeded")
        finalize.assert_called_once_with(
            user_id=12,
            row_id=row.pk,
            request_id=request_id,
            audio=b"mock-audio",
            store=store,
        )
        finish.assert_not_called()
