from django.contrib import admin
from .models import Bot
from .models import KnowledgeBase

@admin.register(KnowledgeBase)
class KnowledgeBaseAdmin(admin.ModelAdmin):
    list_display = ("bot", "uploaded_by", "file", "uploaded_at")
    list_filter = ("bot",)


@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name',)
