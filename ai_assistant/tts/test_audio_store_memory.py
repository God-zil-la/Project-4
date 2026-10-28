from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase
from django.utils import timezone

from .audio_store_memory import MemoryAudioStore
from .audio_storage import MAX_AUDIO_BYTES


class MemoryAudioStoreTests(SimpleTestCase):
    def setUp(self):
        self.store = MemoryAudioStore()
        self.key = uuid4()

    def test_save_and_load(self):
        self.store.save(request_id=self.key, audio=b"mock-audio")
        self.assertEqual(
            self.store.load(request_id=self.key),
            b"mock-audio",
        )

    def test_missing_audio(self):
        self.assertIsNone(self.store.load(request_id=self.key))

    def test_delete_audio(self):
        self.store.save(request_id=self.key, audio=b"mock-audio")
        self.store.delete(request_id=self.key)
        self.assertIsNone(self.store.load(request_id=self.key))

    def test_audio_expires_after_fifteen_minutes(self):
        start = timezone.now()
        with patch(
            "ai_assistant.tts.audio_store_memory.timezone.now",
            return_value=start,
        ):
            self.store.save(request_id=self.key, audio=b"mock-audio")

        with patch(
            "ai_assistant.tts.audio_store_memory.timezone.now",
            return_value=start + timedelta(minutes=15),
        ):
            self.assertIsNone(self.store.load(request_id=self.key))

    def test_oversized_audio_rejected(self):
        with self.assertRaisesRegex(ValueError, "audio_too_large"):
            self.store.save(
                request_id=self.key,
                audio=b"x" * (MAX_AUDIO_BYTES + 1),
            )

    def test_empty_audio_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_audio"):
            self.store.save(request_id=self.key, audio=b"")

    def test_repeated_save_does_not_replace_existing_audio(self):
        self.store.save(request_id=self.key, audio=b"first-audio")
        self.store.save(request_id=self.key, audio=b"second-audio")

        self.assertEqual(
            self.store.load(request_id=self.key),
            b"first-audio",
        )
