from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_assistant.accounts'
    label = 'ai_accounts'

    def ready(self):
        import ai_assistant.accounts.signals 
