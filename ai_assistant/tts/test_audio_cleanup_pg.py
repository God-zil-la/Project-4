import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from ai_assistant.tts.audio_cleanup_pg import (
    PostgresAudioRepository, StorageLimits,
    _validate_request,
)


class PostgresRepositoryContractTests(unittest.TestCase):
    def setUp(self):
        limits = StorageLimits(
            max_bytes=8388608,
            max_objects=10,
            max_uploads_per_day=100,
        )
        self.repo = PostgresAudioRepository(
            global_limits=limits,
            account_limits=limits,
        )

    def test_valid_reservation_fields(self):
        _validate_request(
            uuid4(), 1, 1024,
            datetime.now(timezone.utc) + timedelta(minutes=15),
        )

    def test_oversized_audio_rejected(self):
        with self.assertRaises(ValueError):
            _validate_request(
                uuid4(), 1, 8388609,
                datetime.now(timezone.utc),
            )

    def test_invalid_account_rejected(self):
        with self.assertRaises(ValueError):
            _validate_request(
                uuid4(), 0, 100,
                datetime.now(timezone.utc),
            )

    def test_naive_expiry_rejected(self):
        with self.assertRaises(ValueError):
            _validate_request(
                uuid4(), 1, 100, datetime(2026, 10, 16),
            )

    def test_invalid_limit_rejected(self):
        with self.assertRaises(ValueError):
            StorageLimits(0, 1, 1)

    def test_scopes(self):
        self.assertEqual(
            self.repo._scopes(42),
            ("global", "account:42"),
        )


if __name__ == "__main__":
    unittest.main()
