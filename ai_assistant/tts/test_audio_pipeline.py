from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from .audio_pipeline import store_synthesized_audio


class AudioPipelineTests(SimpleTestCase):
    @patch("ai_assistant.tts.audio_pipeline.finalize_stored_audio")
    def test_pipeline_delegates_to_safe_finalization(self, finalize):
        request_id = uuid4()
        row_id = uuid4()
        store = object()
        expected = object()
        finalize.return_value = expected

        result = store_synthesized_audio(
            user_id=12,
            row_id=row_id,
            request_id=request_id,
            audio=b"mock-audio",
            store=store,
        )

        self.assertIs(result, expected)
        finalize.assert_called_once_with(
            user_id=12,
            row_id=row_id,
            request_id=request_id,
            audio=b"mock-audio",
            store=store,
        )

    @patch("ai_assistant.tts.audio_finalization.service.finish")
    def test_pipeline_stores_audio_before_success(self, finish):
        from .audio_store_memory import MemoryAudioStore

        store = MemoryAudioStore()
        request_id = uuid4()
        row_id = uuid4()
        events = []

        def record_finish(**kwargs):
            self.assertEqual(store.load(request_id=row_id), b"mock-audio")
            events.append(kwargs["state"])
            return "finalized"

        finish.side_effect = record_finish

        result = store_synthesized_audio(
            user_id=12,
            row_id=row_id,
            request_id=request_id,
            audio=b"mock-audio",
            store=store,
        )

        self.assertEqual(result, "finalized")
        self.assertEqual(events, ["succeeded"])
        self.assertEqual(store.load(request_id=row_id), b"mock-audio")
