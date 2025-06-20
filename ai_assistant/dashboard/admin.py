import csv
from django.http import HttpResponse
from django.contrib import admin
from django.contrib.admin import DateFieldListFilter
from ai_assistant.dashboard.models import BotUsageLog

# Unregister first if already registered (to avoid AlreadyRegistered error)
try:
    admin.site.unregister(BotUsageLog)
except admin.sites.NotRegistered:
    pass


@admin.register(BotUsageLog)
class BotUsageLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'bot', 'token_count', 'timestamp')
    list_filter = (
        'bot',
        'user',
        ('timestamp', DateFieldListFilter),
    )
    search_fields = ('user__username', 'bot__name', 'message')
    actions = ['export_as_csv']

    @admin.action(description="Export selected logs as CSV")
    def export_as_csv(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="bot_usage_logs.csv"'

        writer = csv.writer(response)
        writer.writerow(['User', 'Bot', 'Message', 'Token Count', 'Timestamp'])

        for log in queryset:
            writer.writerow([
                log.user.username,
                log.bot.name,
                log.message,
                log.token_count,
                log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            ])

        return response
