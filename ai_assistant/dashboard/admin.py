"""
Admin configuration for the BotUsageLog model in the dashboard app.

Includes:
- Search and filter features for log entries.
- CSV export functionality.
"""

import csv
from django.http import HttpResponse
from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from ai_assistant.dashboard.models import BotUsageLog

# Ensure the model isn't already registered before re-registering
try:
    admin.site.unregister(BotUsageLog)
except admin.sites.NotRegistered:
    pass


@admin.register(BotUsageLog)
class BotUsageLogAdmin(admin.ModelAdmin):
    """
    Custom admin interface for viewing and exporting BotUsageLog entries.

    Features:
    - List display of user, bot, tokens used, and timestamp.
    - Filters by user, bot, and timestamp.
    - CSV export action for selected entries.
    """
    list_display = ('user', 'bot', 'tokens_used', 'timestamp')
    list_filter = (
        'bot',
        'user',
        ('timestamp', DateFieldListFilter),
    )
    search_fields = ('user__username', 'bot__name')
    actions = ['export_as_csv']

    @admin.action(description="Export selected logs as CSV")
    def export_as_csv(self, request, queryset):
        """
        Export selected BotUsageLog records to a downloadable CSV file.

        Args:
            request (HttpRequest): The admin request object.
            queryset (QuerySet): Selected log entries.

        Returns:
            HttpResponse: CSV file for download.
        """
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = (
            'attachment; filename="bot_usage_logs.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(['User', 'Bot', 'Tokens Used', 'Timestamp'])

        for log in queryset:
            writer.writerow([
                log.user.username,
                log.bot.name,
                log.tokens_used,
                log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            ])

        return response
