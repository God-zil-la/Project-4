"""Offline security regression tests for the optional OpenAI TTS adapter."""
from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import patch

import httpx

from .errors import TTSError
from .provider_openai import OpenAITTSProvider


class OpenAITTSProviderTests(TestCase):
    def synthesize_with_response(self, data, content_type="audio/mpeg"):
        @contextmanager
        def fake_stream(client, method, url, **kwargs):
            response = httpx.Response(
                200,
                request=httpx.Request(method, url),
                content=data,
                headers={"content-type": content_type},
            )
            yield response

        with patch.dict("os.environ", {
            "U62_REAL_TTS_ENABLED": "true",
            "OPENAI_API_KEY": "fake-test-key",
        }):
            with patch.object(httpx.Client, "stream", fake_stream):
                return OpenAITTSProvider(
                    allow_paid_calls=True
                ).synthesize("Test response")

    def test_disabled_by_default(self):
        with patch.dict("os.environ", {
            "U62_REAL_TTS_ENABLED": "false",
        }):
            with patch.object(httpx.Client, "stream") as stream:
                with self.assertRaisesRegex(TTSError, "real_tts_disabled"):
                    OpenAITTSProvider(
                        allow_paid_calls=True
                    ).synthesize("Test")
                stream.assert_not_called()

    def test_rejects_json_response(self):
        with self.assertRaisesRegex(TTSError, "invalid_tts_content_type"):
            self.synthesize_with_response(
                b'{"error":"not audio"}', "application/json"
            )

    def test_rejects_fake_mp3(self):
        with self.assertRaisesRegex(TTSError, "invalid_tts_audio"):
            self.synthesize_with_response(b"not-an-mp3")

    def test_rejects_oversized_response(self):
        with self.assertRaisesRegex(TTSError, "tts_audio_too_large"):
            self.synthesize_with_response(
                b"ID3" + b"x" * (8 * 1024 * 1024)
            )

    def test_accepts_mp3_signature(self):
        audio = b"ID3" + b"\x03\x00\x00" + b"\x00" * 16
        self.assertEqual(self.synthesize_with_response(audio), audio)
