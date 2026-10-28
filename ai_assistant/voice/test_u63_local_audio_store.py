from uuid import UUID, uuid4
"""U6.3 local audio storage security tests."""

import os
import time
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from ai_assistant.voice.local_audio_store import LocalVoiceAudioStore


MP3 = b"ID3" + b"\x04\x00\x00\x00\x00\x00\x00" + b"test-audio"


class LocalAudioStoreTests(TestCase):

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)

        self.settings_patch = patch(
            "ai_assistant.voice.local_audio_store.settings.BASE_DIR",
            Path(self.directory.name),
        )
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)

    def test_save_and_load(self):
        store = LocalVoiceAudioStore(user_id=10)
        store.save(request_id=UUID(int=101), audio=MP3)
        self.assertEqual(store.load(request_id=UUID(int=101)), MP3)

    def test_user_isolation(self):
        first = LocalVoiceAudioStore(user_id=10)
        second = LocalVoiceAudioStore(user_id=11)

        first.save(request_id=UUID(int=101), audio=MP3)

        self.assertIsNone(second.load(request_id=UUID(int=101)))

    def test_reject_invalid_request_id(self):
        store = LocalVoiceAudioStore(user_id=10)

        for value in ("../101", 0, -1, True):
            with self.assertRaises(ValueError):
                store.load(request_id=value)

    def test_reject_invalid_mp3(self):
        store = LocalVoiceAudioStore(user_id=10)

        with self.assertRaises(ValueError):
            store.save(request_id=UUID(int=101), audio=b"not-mp3")

    def test_prevent_overwrite(self):
        store = LocalVoiceAudioStore(user_id=10)

        store.save(request_id=UUID(int=101), audio=MP3)

        with self.assertRaises(FileExistsError):
            store.save(request_id=UUID(int=101), audio=MP3)

        self.assertEqual(store.load(request_id=UUID(int=101)), MP3)

    def test_expired_audio_unavailable(self):
        store = LocalVoiceAudioStore(user_id=10)

        store.save(request_id=UUID(int=101), audio=MP3)

        path = store._path(UUID(int=101))
        old = time.time() - 16 * 60
        os.utime(path, (old, old))

        self.assertIsNone(store.load(request_id=UUID(int=101)))

    def test_missing_audio(self):
        store = LocalVoiceAudioStore(user_id=10)

        self.assertIsNone(store.load(request_id=UUID(int=999)))
