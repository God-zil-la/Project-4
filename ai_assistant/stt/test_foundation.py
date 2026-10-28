import io
import struct
import unittest
import wave
from unittest.mock import MagicMock, patch

import requests

from .audio import InvalidAudio, validated_wav
from .client import TranscriptionError, transcribe
from .policy import STT_MINUTES, stt_limit_ms


def wav_bytes(frames=8000):
    output = io.BytesIO()
    with wave.open(output, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(8000)
        wav.writeframes(b'\0\0' * frames)
    return output.getvalue()


class AudioTests(unittest.TestCase):
    def reject(self, payload):
        with self.assertRaises(InvalidAudio), validated_wav(io.BytesIO(payload)):
            self.fail('invalid audio accepted')

    def test_sha256_matches_validated_audio_bytes(self):
        from hashlib import sha256

        first = wav_bytes(8000)
        second = wav_bytes(8001)

        with validated_wav(io.BytesIO(first)) as audio:
            self.assertEqual(audio.sha256, sha256(first).hexdigest())
            self.assertEqual(audio.file.read(), first)

        with validated_wav(io.BytesIO(second)) as audio:
            self.assertEqual(audio.sha256, sha256(second).hexdigest())
            self.assertNotEqual(audio.sha256, sha256(first).hexdigest())

    def test_duration_uses_actual_frames_and_rounds_up(self):
        with validated_wav(io.BytesIO(wav_bytes(8001))) as audio:
            self.assertEqual(audio.milliseconds, 1001)
            self.assertEqual(audio.file.read(4), b'RIFF')
        self.assertTrue(audio.file.closed)

    def test_cleanup_after_downstream_failure(self):
        with self.assertRaises(RuntimeError):
            with validated_wav(io.BytesIO(wav_bytes())) as audio:
                raise RuntimeError()
        self.assertTrue(audio.file.closed)

    def test_cleanup_after_invalid_upload(self):
        file = io.BytesIO()
        with patch('ai_assistant.stt.audio.tempfile.TemporaryFile', return_value=file):
            self.reject(b'invalid')
        self.assertTrue(file.closed)

    def test_empty_and_spoofed_files(self):
        for payload in (b'', b'not audio', b'RIFF\0\0\0\0WAVE', wav_bytes(0)):
            with self.subTest(payload=payload[:12]):
                self.reject(payload)

    def test_truncation_and_trailing_bytes(self):
        self.reject(wav_bytes()[:-1])
        self.reject(wav_bytes() + b'junk')

    def test_lying_data_length(self):
        payload = bytearray(wav_bytes())
        payload[40:44] = struct.pack('<I', 16002)
        self.reject(payload)

    def test_inconsistent_pcm_parameters(self):
        payload = bytearray(wav_bytes())
        payload[28:32] = struct.pack('<I', 42)
        self.reject(payload)

    def test_duplicate_audio_payload(self):
        payload = bytearray(wav_bytes())
        payload.extend(b'data' + struct.pack('<I', 2) + b'\0\0')
        payload[4:8] = struct.pack('<I', len(payload) - 8)
        self.reject(payload)

    def test_duration_boundary(self):
        with patch('ai_assistant.stt.audio.MAX_SECONDS', 1):
            with validated_wav(io.BytesIO(wav_bytes())) as audio:
                self.assertEqual(audio.milliseconds, 1000)
            self.reject(wav_bytes(8001))

    def test_size_enforced_from_bytes(self):
        with patch('ai_assistant.stt.audio.MAX_BYTES', 100):
            self.reject(wav_bytes())


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.session = MagicMock()
        self.session.__enter__.return_value = self.session
        self.response = MagicMock(status_code=200)
        self.response.__enter__.return_value = self.response
        self.response.iter_content.return_value = [b'{"text":"Hej"}']
        self.session.post.return_value = self.response
        self.patch = patch('ai_assistant.stt.client.requests.Session', return_value=self.session)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def call(self, key='test-only'):
        with validated_wav(io.BytesIO(wav_bytes())) as audio:
            return transcribe(audio, api_key=key)

    def test_success_fixed_model_and_url(self):
        self.assertEqual(self.call(), 'Hej')
        args, kwargs = self.session.post.call_args
        self.assertEqual(args[0], 'https://api.openai.com/v1/audio/transcriptions')
        self.assertEqual(kwargs['data'], {'model': 'gpt-transcribe', 'response_format': 'json'})
        self.assertEqual(kwargs['timeout'], (5, 45))
        self.assertFalse(kwargs['allow_redirects'])
        self.assertFalse(self.session.trust_env)
        self.assertTrue(kwargs['files']['file'][1].closed)
        self.response.__exit__.assert_called_once()

    def test_no_credentials_no_request(self):
        with self.assertRaises(TranscriptionError) as context:
            self.call('')
        self.assertFalse(context.exception.uncertain)
        self.session.post.assert_not_called()

    def test_timeout_and_network_errors_are_uncertain_and_never_retried(self):
        for error in (requests.Timeout('secret'), requests.ConnectionError('secret')):
            with self.subTest(error=type(error)):
                self.session.post.reset_mock()
                self.session.post.side_effect = error
                with self.assertRaises(TranscriptionError) as context:
                    self.call()
                self.assertTrue(context.exception.uncertain)
                self.assertNotIn('secret', str(context.exception))
                self.session.post.assert_called_once()

    def test_provider_errors_and_redirects_not_exposed(self):
        for status in (301, 400, 401, 429, 500):
            self.response.status_code = status
            with self.assertRaises(TranscriptionError) as context:
                self.call()
            self.assertEqual(context.exception.code, 'stt_provider_error')
            self.assertTrue(context.exception.uncertain)
        self.response.iter_content.assert_not_called()

    def test_invalid_json_and_schema(self):
        for body in (b'invalid', b'[]', b'{}', b'{"text":42}', b'\xff'):
            self.response.iter_content.return_value = [body]
            with self.assertRaises(TranscriptionError) as context:
                self.call()
            self.assertEqual(context.exception.code, 'stt_invalid_response')

    def test_response_size_bound(self):
        with patch('ai_assistant.stt.client.MAX_RESPONSE_BYTES', 5):
            with self.assertRaises(TranscriptionError):
                self.call()

    def test_elapsed_time_guard(self):
        with patch('ai_assistant.stt.client.time.monotonic', side_effect=[0, 51]):
            with self.assertRaises(TranscriptionError) as context:
                self.call()
        self.assertEqual(context.exception.code, 'stt_timeout')


class PolicyTests(unittest.TestCase):
    def test_locked_stt_quotas(self):
        self.assertEqual(STT_MINUTES, {'free': 0, 'premium': 120, 'pro': 300,
                                      'business': 600, 'business_max': 1200})
        self.assertEqual(stt_limit_ms('premium'), 7_200_000)
        self.assertEqual(stt_limit_ms('pro'), 18_000_000)

    def test_unlaunched_unknown_and_free_have_no_access(self):
        for plan in ('free', 'business', 'business_max', 'unknown', None):
            self.assertEqual(stt_limit_ms(plan), 0)


if __name__ == '__main__':
    unittest.main()
