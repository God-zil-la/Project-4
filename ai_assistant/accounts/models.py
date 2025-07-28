from django.db import models
from django.contrib.auth.models import User
from datetime import date
import secrets


class UserProfile(models.Model):
    """Extended profile model linked to Django's User with subscription and usage tracking."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_subscribed = models.BooleanField(default=False)
    daily_message_count = models.IntegerField(default=0)
    last_reset = models.DateField(default=date.today)
    api_key = models.CharField(max_length=64, unique=True, blank=True)

    def reset_daily_count(self):
        """Reset the message count if the last reset was on a previous day."""
        if self.last_reset != date.today():
            self.daily_message_count = 0
            self.last_reset = date.today()
            self.save(update_fields=['daily_message_count', 'last_reset'])

    def increment_message_count(self):
        """Increment the daily message count by 1."""
        self.daily_message_count += 1
        self.save(update_fields=['daily_message_count'])

    def generate_api_key(self):
        """Generate and save a new API key for the user."""
        self.api_key = secrets.token_hex(32)
        self.save(update_fields=['api_key'])

    def __str__(self):
        """Return a readable string representation of the profile."""
        return f"{self.user.username} Profile"
