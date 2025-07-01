from django.urls import path
from . import views
from .views import upload_knowledge

app_name = 'bots'

urlpatterns = [
    path('my-bots/', views.my_bots, name='my-bots'),
    path('', views.bot_list, name='list'),
    path('create/', views.create_bot, name='create'),
    path('<int:bot_id>/edit/', views.edit_bot, name='edit'),
    path('<int:bot_id>/delete/', views.delete_bot, name='delete'),
    path('<int:bot_id>/playground/', views.bot_chat_playground, name='playground'),
    path('<int:bot_id>/bot_chat_api/', views.bot_chat_api, name='bot_chat_api'),  # <-- FIXED
    path('<int:bot_id>/ajax_chat/', views.ajax_chat, name='ajax_chat'),
    path('admin-dashboard/', views.admin_dashboard, name='admin-dashboard'),
    path('analytics/', views.analytics_dashboard, name='analytics'),
    path('<int:bot_id>/upload-knowledge/', upload_knowledge, name='upload_knowledge'),
]
