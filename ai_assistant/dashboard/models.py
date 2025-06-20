from django.db import models
from django.contrib.auth.models import User
from ai_assistant.bots.models import Bot

class BotUsageLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE)
    message = models.TextField()
    token_count = models.IntegerField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} used {self.bot.name} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
