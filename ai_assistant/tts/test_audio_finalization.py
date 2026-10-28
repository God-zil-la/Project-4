from unittest.mock import Mock, call, patch
from uuid import uuid4

from django.test import SimpleTestCase

from .audio_finalization import finalize_stored_audio


class AudioFinalizationTests(SimpleTestCase):
    def setUp(self):
        self.store = Mock()
        self.request_id = uuid4()
        self.row_id = uuid4()
        self.args = {
            "user_id": 12,
            "row_id": self.row_id,
            "request_id": self.request_id,
            "audio": b"mock-audio",
            "store": self.store,
        }

    @patch("ai_assistant.tts.audio_finalization.service.finish")
    def test_success_saves_before_finalizing(self, finish):
        events = []
        self.store.save.side_effect = lambda **kwargs: events.append("save")
        finish.side_effect = lambda **kwargs: events.append("finish")

        finalize_stored_audio(**self.args)

        self.assertEqual(events, ["save", "finish"])
        self.store.save.assert_called_once_with(
            request_id=self.row_id,
            audio=b"mock-audio",
        )
        self.assertEqual(finish.call_args.kwargs["state"], "succeeded")

    @patch("ai_assistant.tts.audio_finalization.service.finish")
    def test_storage_failure_does_not_mark_success(self, finish):
        self.store.save.side_effect = OSError("storage unavailable")

        with self.assertRaises(OSError):
            finalize_stored_audio(**self.args)

        finish.assert_called_once_with(
            user_id=12,
            row_id=self.row_id,
            state="uncertain",
        )

    @patch("ai_assistant.tts.audio_finalization.service.finish")
    def test_database_failure_retains_audio_for_recovery(self, finish):
        finish.side_effect = RuntimeError("database unavailable")

        with self.assertRaises(RuntimeError):
            finalize_stored_audio(**self.args)

        self.store.delete.assert_not_called()

    @patch("ai_assistant.tts.audio_finalization.service.finish")
    def test_invalid_audio_never_reaches_storage(self, finish):
        self.args["audio"] = b""

        with self.assertRaises(ValueError):
            finalize_stored_audio(**self.args)

        self.store.save.assert_not_called()
        finish.assert_not_called()

    @patch("ai_assistant.tts.audio_finalization.service.finish")
    def test_database_failure_does_not_attempt_destructive_cleanup(self, finish):
        finish.side_effect = RuntimeError("database unavailable")
        self.store.delete.side_effect = OSError("cleanup unavailable")

        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            finalize_stored_audio(**self.args)

        self.store.save.assert_called_once()
        self.store.delete.assert_not_called()
        finish.assert_called_once_with(
            user_id=12,
            row_id=self.row_id,
            state="succeeded",
        )
