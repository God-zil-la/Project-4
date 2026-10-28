import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
from uuid import uuid4

from ai_assistant.voice.local_audio_store import LocalVoiceAudioStore


class U63MP3RoundtripTests(TestCase):

    def test_mp3_save_and_load_roundtrip(self):
        audio = bytes([0xFF, 0xFB, 0x90, 0x64]) + bytes(512)
        request_id = uuid4()

        with tempfile.TemporaryDirectory() as temporary:
            with patch(
                "ai_assistant.voice.local_audio_store.settings.BASE_DIR",
                Path(temporary),
            ):
                store = LocalVoiceAudioStore(user_id=123456)
                store.save(request_id=request_id, audio=audio)
                recovered = store.load(request_id=request_id)

                self.assertEqual(recovered, audio)
                self.assertTrue(
                    store._path(request_id).is_file()
                )

    def test_missing_mp3_returns_none(self):
        with tempfile.TemporaryDirectory() as temporary:
            with patch(
                "ai_assistant.voice.local_audio_store.settings.BASE_DIR",
                Path(temporary),
            ):
                store = LocalVoiceAudioStore(user_id=123456)
                self.assertIsNone(
                    store.load(request_id=uuid4())
                )
