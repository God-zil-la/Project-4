# ai_assistant/payments/apps.py
from django.apps import AppConfig

class PaymentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_assistant.payments'
    label = 'ai_payments'  # ensure this is unique among all apps
