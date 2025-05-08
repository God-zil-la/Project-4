from django.db import models
from django.contrib.auth.models import User


class Bot(models.Model):
    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('fitness', 'Fitness'),
        ('finance', 'Finance'),
        ('funny', 'Funny'),
        ('support', 'Support'),
        ('tech', 'Tech'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    personality = models.TextField(default="I am a helpful and friendly assistant.")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')

    def __str__(self):
        return self.name


class ChatMessage(models.Model):
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name='chat_messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    sender = models.CharField(max_length=10, choices=[('user', 'User'), ('bot', 'Bot')])
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender}: {self.message[:50]}"
