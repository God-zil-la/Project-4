from django.db import models
from django.contrib.auth.models import User
from ai_assistant.bots.models import Bot


class BotUsageLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='dashboard_bot_usage_logs'
    )
    bot = models.ForeignKey(
        Bot,
        on_delete=models.CASCADE,
        related_name='dashboard_bot_usage_logs'
    )
    tokens_used = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.user.username} used {self.tokens_used} tokens on "
            f"{self.timestamp}"
        )
