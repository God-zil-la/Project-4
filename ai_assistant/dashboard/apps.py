from django.apps import AppConfig
from django.contrib.admin.apps import AdminConfig

class DashboardAdminConfig(AdminConfig):
    default_site = 'ai_assistant.dashboard.admin.CustomAdminSite'

class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ai_assistant.dashboard'
    label = 'ai_dashboard' 
