from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_assistant.dashboard'
    label = 'ai_dashboard'  # <-- Unique label added here
