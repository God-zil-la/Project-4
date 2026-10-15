from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from ai_assistant.bots.premium_discord_worker import process_next


class PremiumDiscordWorkerTests(SimpleTestCase):

    def make_job(self):
        job = MagicMock()
        job.guild_id = "123"
        job.application_id = "456"
        job.interaction_id = "test-interaction-123"
        job.prompt = "Hello"
        job.status = "processing"
        job.created_at = timezone.now() - timedelta(seconds=10)
        return job

    @patch("ai_assistant.bots.premium_discord_worker.finish_interaction")
    @patch("ai_assistant.bots.premium_discord_worker.requests.post")
    @patch("ai_assistant.bots.premium_discord_worker.answer_premium_discord")
    @patch("ai_assistant.bots.premium_discord_worker.decrypt_token")
    @patch("ai_assistant.bots.premium_discord_worker.claim_interaction")
    def test_successful_job(self, claim, decrypt, answer, post, finish):
        job = self.make_job()
        claim.return_value = job
        decrypt.return_value = "fake-token"
        answer.return_value = "Hello from AI Assistant"

        self.assertTrue(process_next())

        answer.assert_called_once_with(guild_id="123", message="Hello")
        post.assert_called_once()
        finish.assert_called_once_with(job, "done")

    @patch("ai_assistant.bots.premium_discord_worker.claim_interaction")
    def test_empty_queue(self, claim):
        claim.return_value = None
        self.assertFalse(process_next())

    @patch("ai_assistant.bots.premium_discord_worker.finish_interaction")
    @patch("ai_assistant.bots.premium_discord_worker.requests.post")
    @patch("ai_assistant.bots.premium_discord_worker.answer_premium_discord")
    @patch("ai_assistant.bots.premium_discord_worker.decrypt_token")
    @patch("ai_assistant.bots.premium_discord_worker.claim_interaction")
    def test_expired_status_blocks_delivery(
        self, claim, decrypt, answer, post, finish
    ):
        job = self.make_job()
        job.status = "expired"
        claim.return_value = job
        decrypt.return_value = "fake-token"
        answer.return_value = "AI response"

        self.assertTrue(process_next())
        post.assert_not_called()
        finish.assert_called_once_with(job, "failed")

    @patch("ai_assistant.bots.premium_discord_worker.finish_interaction")
    @patch("ai_assistant.bots.premium_discord_worker.requests.post")
    @patch("ai_assistant.bots.premium_discord_worker.answer_premium_discord")
    @patch("ai_assistant.bots.premium_discord_worker.decrypt_token")
    @patch("ai_assistant.bots.premium_discord_worker.claim_interaction")
    def test_old_job_blocks_delivery(
        self, claim, decrypt, answer, post, finish
    ):
        job = self.make_job()
        job.created_at = timezone.now() - timedelta(minutes=16)
        claim.return_value = job
        decrypt.return_value = "fake-token"
        answer.return_value = "AI response"

        self.assertTrue(process_next())
        post.assert_not_called()
        finish.assert_called_once_with(job, "failed")
