from django.contrib import admin
from .models import Bot
from .models import KnowledgeBase
from .models import BotTemplate
from .models import AIResponseReport


@admin.register(AIResponseReport)
class AIResponseReportAdmin(admin.ModelAdmin):
    """Evidence is immutable; review edits use Django's admin audit log."""

    list_display = ("id", "original_message_id", "reporter", "created_at", "status")
    list_filter = ("status", "created_at")
    readonly_fields = (
        "reporter", "message", "original_message_id", "conversation_id_snapshot",
        "response_text", "response_created_at", "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    """
    Admin configuration for the KnowledgeBase model.
    Displays bot, uploader, file, and upload time in the admin list view.
    """
    list_display = ("bot", "uploaded_by", "file", "uploaded_at")
    list_filter = ("bot",)


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    """
    Admin configuration for the Bot model.
    Displays name, description, and creation time. Enables search by name.
    """
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name',)


@admin.register(BotTemplate)
class BotTemplateAdmin(admin.ModelAdmin):
    """
    Admin configuration for the BotTemplate model.
    Displays name, description, and category. Enables search by name and category.
    """
    list_display = ('name', 'description', 'category')
    search_fields = ('name', 'category')
