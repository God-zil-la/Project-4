"""Offline security tests for Premium Discord OAuth state binding."""
from unittest.mock import patch

from django.core import signing
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from .premium_discord_oauth import (
    STATE_MAX_AGE_SECONDS,
    STATE_SALT,
    create_oauth_state,
    validate_oauth_state,
)


class PremiumDiscordOAuthStateTests(SimpleTestCase):
    def test_round_trip_and_account_binding(self):
        state = create_oauth_state(42)
        self.assertEqual(validate_oauth_state(state, 42), 42)
        with self.assertRaises(ValidationError):
            validate_oauth_state(state, 43)

    def test_forged_or_malformed_state_rejected(self):
        state = create_oauth_state(42)
        for invalid in ("", state + "x", "invalid", None, "x" * 4097):
            with self.subTest(state=str(invalid)[:16]):
                with self.assertRaises(ValidationError):
                    validate_oauth_state(invalid, 42)

    def test_expired_state_rejected(self):
        with patch("django.core.signing.time.time", return_value=1000):
            state = create_oauth_state(42)
        with patch("django.core.signing.time.time", return_value=1000 + STATE_MAX_AGE_SECONDS + 1):
            with self.assertRaises(ValidationError):
                validate_oauth_state(state, 42)

    def test_unexpected_payload_and_ids_rejected(self):
        for user_id in (0, -1, True, "nope"):
            with self.assertRaises(ValueError):
                create_oauth_state(user_id)
        state = signing.dumps({"uid": True}, salt=STATE_SALT)
        with self.assertRaises(ValidationError):
            validate_oauth_state(state, True)
        state = signing.dumps({"guild_id": "123"}, salt=STATE_SALT)
        with self.assertRaises(ValidationError):
            validate_oauth_state(state, 42)
