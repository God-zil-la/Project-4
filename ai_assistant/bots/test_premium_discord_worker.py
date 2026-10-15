from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from ai_assistant.bots.premium_discord_worker import process_next


class PremiumDiscordWorkerTests(SimpleTestCase):

    @patch("ai_assistant.bots.premium_discord_worker.finish_interaction")
    @patch("ai_assistant.bots.premium_discord_worker.requests.post")
    @patch("ai_assistant.bots.premium_discord_worker.answer_premium_discord")
    @patch("ai_assistant.bots.premium_discord_worker.decrypt_token")
    @patch("ai_assistant.bots.premium_discord_worker.claim_interaction")
    def test_successful_job(self, claim, decrypt, answer, post, finish):
        job = MagicMock()
        job.guild_id = "123"
        job.application_id = "456"
        job.prompt = "Hello"
        claim.return_value = job
        decrypt.return_value = "fake-token"
        answer.return_value = "Hello from AI Assistant"
        post.return_value.raise_for_status.return_value = None

        self.assertTrue(process_next())
        answer.assert_called_once_with(guild_id="123", message="Hello")
        finish.assert_called_once_with(job, "done")

    @patch("ai_assistant.bots.premium_discord_worker.claim_interaction")
    def test_empty_queue(self, claim):
        claim.return_value = None
        self.assertFalse(process_next())
