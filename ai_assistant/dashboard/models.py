from django.db import models
from django.contrib.auth.models import User

from ai_assistant.bots.models import Bot


class BotUsageLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="dashboard_bot_usage_logs",
    )

    bot = models.ForeignKey(
        Bot,
        on_delete=models.CASCADE,
        related_name="dashboard_bot_usage_logs",
    )

    # Total tokens used for this AI request.
    # Kept for backwards compatibility with existing logs.
    tokens_used = models.IntegerField()

    # Separate token counts let us calculate actual API cost,
    # since input and output tokens have different prices.
    input_tokens = models.IntegerField(default=0)
    output_tokens = models.IntegerField(default=0)

    # Store which OpenAI model handled the request.
    model = models.CharField(
        max_length=100,
        default="unknown",
    )

    timestamp = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return (
            f"{self.user.username} used "
            f"{self.tokens_used} tokens with "
            f"{self.model} on {self.timestamp}"
        )