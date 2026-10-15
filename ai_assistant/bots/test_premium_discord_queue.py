from datetime import timedelta
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.test import TestCase
from django.utils import timezone

from ai_assistant.bots.premium_discord_models import PremiumDiscordJob
from ai_assistant.bots.premium_discord_queue import (
    enqueue_interaction,
    claim_interaction,
    decrypt_token,
    finish_interaction,
    expire_stale_interactions,
)


class PremiumDiscordQueueTests(TestCase):

    def setUp(self):
        self.key = Fernet.generate_key().decode("ascii")
        self.env = patch.dict(
            "os.environ",
            {"PREMIUM_DISCORD_QUEUE_KEY": self.key},
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def enqueue(self, interaction_id="123"):
        return enqueue_interaction(
            interaction_id=interaction_id,
            guild_id="456",
            application_id="789",
            token="fake-discord-token",
            prompt="Hello AI Assistant",
        )

    def test_token_is_encrypted(self):
        self.assertTrue(self.enqueue())
        job = PremiumDiscordJob.objects.get(interaction_id="123")
        self.assertNotIn("fake-discord-token", job.encrypted_token)
        self.assertEqual(decrypt_token(job), "fake-discord-token")

    def test_duplicate_interaction_is_rejected(self):
        self.assertTrue(self.enqueue())
        self.assertFalse(self.enqueue())
        self.assertEqual(
            PremiumDiscordJob.objects.filter(interaction_id="123").count(),
            1,
        )

    def test_job_can_be_claimed_and_completed(self):
        self.enqueue()
        job = claim_interaction()
        self.assertIsNotNone(job)
        self.assertEqual(job.status, "processing")

        finish_interaction(job, "done")
        job.refresh_from_db()

        self.assertEqual(job.status, "done")
        self.assertEqual(job.encrypted_token, "")
        self.assertEqual(job.prompt, "")

    def test_empty_queue_returns_none(self):
        self.assertIsNone(claim_interaction())

    def test_stale_processing_job_expires_without_retry(self):
        self.enqueue("crashed-worker")
        job = claim_interaction()
        self.assertEqual(job.status, "processing")

        PremiumDiscordJob.objects.filter(pk=job.pk).update(
            created_at=timezone.now() - timedelta(minutes=16)
        )

        expired_count = expire_stale_interactions()
        job.refresh_from_db()

        self.assertEqual(expired_count, 1)
        self.assertEqual(job.status, "expired")
        self.assertEqual(job.encrypted_token, "")
        self.assertEqual(job.prompt, "")
        self.assertIsNone(claim_interaction())
