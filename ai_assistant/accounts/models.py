from django.db import models
from django.contrib.auth.models import User
from datetime import date


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    is_subscribed = models.BooleanField(default=False)
    daily_message_count = models.IntegerField(default=0)
    last_reset = models.DateField(default=date.today)

    def reset_daily_count(self):
        if self.last_reset != date.today():
            self.daily_message_count = 0
            self.last_reset = date.today()
            self.save()

    def increment_message_count(self):
        self.daily_message_count += 1
        self.save()

    def __str__(self):
        return f"{self.user.username} Profile"
