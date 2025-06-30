from django.urls import path
from . import views
from .views import upload_knowledge

app_name = 'bots'

urlpatterns = [
    # Path for viewing the user's bots
    path('my-bots/', views.my_bots, name='my-bots'),
    
    # Path for listing all bots
    path('', views.bot_list, name='list'),
    
    # Path for creating a new bot
    path('create/', views.create_bot, name='create'),
    
    # Paths for editing, deleting specific bots by bot_id
    path('<int:bot_id>/edit/', views.edit_bot, name='edit'),
    path('<int:bot_id>/delete/', views.delete_bot, name='delete'),
    
    # Path for the chat playground for a specific bot
    path('<int:bot_id>/playground/', views.bot_chat_playground, name='playground'),
    
    # Path for the bot chat API (AJAX)
    path('<int:bot_id>/api/', views.bot_chat_api, name='bot_chat_api'),
    
    # Path for AJAX chat functionality
    path('<int:bot_id>/ajax_chat/', views.ajax_chat, name='ajax_chat'),
    
    # Admin dashboard for managing bot data
    path('admin-dashboard/', views.admin_dashboard, name='admin-dashboard'),
    
    # Analytics dashboard for viewing usage statistics
    path('analytics/', views.analytics_dashboard, name='analytics'),
    
    # Path for uploading knowledge files to a specific bot
    path('<int:bot_id>/upload-knowledge/', upload_knowledge, name='upload_knowledge'),
]
