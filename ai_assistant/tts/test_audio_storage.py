from django.test import SimpleTestCase

from .audio_storage import AUDIO_TTL, MAX_AUDIO_BYTES, validate_audio


class AudioStorageTests(SimpleTestCase):
    def test_valid_audio(self):
        validate_audio(b"mock-audio")
        validate_audio(b"x" * MAX_AUDIO_BYTES)

    def test_empty_audio_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_audio"):
            validate_audio(b"")

    def test_non_bytes_rejected(self):
        for value in (None, "audio", bytearray(b"audio")):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "invalid_audio"):
                    validate_audio(value)

    def test_oversized_audio_rejected(self):
        with self.assertRaisesRegex(ValueError, "audio_too_large"):
            validate_audio(b"x" * (MAX_AUDIO_BYTES + 1))

    def test_storage_limits(self):
        self.assertEqual(MAX_AUDIO_BYTES, 8 * 1024 * 1024)
        self.assertEqual(AUDIO_TTL.total_seconds(), 15 * 60)
