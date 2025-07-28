from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configuration for the accounts app."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_assistant.accounts'

    def ready(self):
        """Import signal handlers when the app is ready."""
        import ai_assistant.accounts.signals
