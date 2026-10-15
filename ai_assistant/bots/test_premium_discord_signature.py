"""Pure signature tests; no external credentials or Discord requests."""
from unittest.mock import patch

from django.test import SimpleTestCase
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from .premium_discord_signature import (
    DiscordInteractionVerificationError, verify_discord_interaction,
)


class DiscordInteractionSignatureTests(SimpleTestCase):
    def setUp(self):
        self.private_key = Ed25519PrivateKey.generate()
        public_key = self.private_key.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        ).hex()
        self.env = patch.dict("os.environ", {"PREMIUM_DISCORD_PUBLIC_KEY": public_key})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_valid_signature(self):
        body, timestamp = b'{"type":1}', "1700000000"
        signature = self.private_key.sign(timestamp.encode() + body).hex()
        self.assertTrue(verify_discord_interaction(
            body=body, signature=signature, timestamp=timestamp, now=1700000000,
        ))

    def test_modified_body_rejected(self):
        body, timestamp = b'{"type":1}', "1700000000"
        signature = self.private_key.sign(timestamp.encode() + body).hex()
        with self.assertRaises(DiscordInteractionVerificationError):
            verify_discord_interaction(
                body=b'{"type":2}', signature=signature,
                timestamp=timestamp, now=1700000000,
            )

    def test_expired_timestamp_rejected(self):
        body, timestamp = b'{"type":1}', "1700000000"
        signature = self.private_key.sign(timestamp.encode() + body).hex()
        with self.assertRaises(DiscordInteractionVerificationError):
            verify_discord_interaction(
                body=body, signature=signature, timestamp=timestamp, now=1700000400,
            )
