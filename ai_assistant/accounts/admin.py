from django.contrib import admin
from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'api_key', 'is_subscribed', 'daily_message_count', 'last_reset')
    search_fields = ('user__username', 'api_key')
