from django.contrib import admin
from .models import Bot

@admin.register(Bot)
class BotAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name',)
