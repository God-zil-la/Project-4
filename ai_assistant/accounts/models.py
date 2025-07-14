from django.db import models
from django.contrib.auth.models import User
from datetime import date
import secrets

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_subscribed = models.BooleanField(default=False)
    daily_message_count = models.IntegerField(default=0)
    last_reset = models.DateField(default=date.today)
    api_key = models.CharField(max_length=64, unique=True, blank=True)

    def reset_daily_count(self):
        if self.last_reset != date.today():
            self.daily_message_count = 0
            self.last_reset = date.today()
            self.save(update_fields=['daily_message_count', 'last_reset'])

    def increment_message_count(self):
        self.daily_message_count += 1
        self.save(update_fields=['daily_message_count'])

    def generate_api_key(self):
        self.api_key = secrets.token_hex(32)
        self.save(update_fields=['api_key'])

    def __str__(self):
        return f"{self.user.username} Profile"
