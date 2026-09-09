from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """Admin interface customization for the UserProfile model."""

    list_display = (
        'user',
        'is_subscribed',
        'daily_message_count',
        'last_reset'
    )
    search_fields = ('user__username',)
    readonly_fields = ('api_key',)
