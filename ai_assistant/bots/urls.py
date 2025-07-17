from django.urls import path
from . import views
from .api_views import (
    BotListCreateAPIView,
    BotDetailAPIView,
    api_bot_chat,
)
from rest_framework.authtoken.views import obtain_auth_token

app_name = 'bots'

urlpatterns = [
    # Regular views
    path('my-bots/', views.my_bots, name='my-bots'),
    path('', views.bot_list, name='list'),
    path('create/', views.create_bot, name='create'),
    path(
        '<int:bot_id>/edit/',
        views.edit_bot,
        name='edit'
    ),
    path(
        '<int:bot_id>/delete/',
        views.delete_bot,
        name='delete'
    ),
    path(
        '<int:bot_id>/playground/',
        views.bot_chat_playground,
        name='playground'
    ),
    path(
        '<int:bot_id>/bot_chat_api/',
        views.bot_chat_api,
        name='bot_chat_api'
    ),
    path(
        '<int:bot_id>/ajax_chat/',
        views.ajax_chat,
        name='ajax_chat'
    ),
    path('analytics/', views.analytics_dashboard, name='analytics'),
    path('admin-dashboard/', views.admin_dashboard, name='admin-dashboard'),

    # API views
    path(
        'api/bots/',
        BotListCreateAPIView.as_view(),
        name='bot-list-create'
    ),
    path(
        'api/bots/<int:pk>/',
        BotDetailAPIView.as_view(),
        name='bot-detail'
    ),
    path(
        'api/token/',
        obtain_auth_token,
        name='get-user-token'
    ),
    path(
        'api/bot/<int:bot_id>/chat/',
        api_bot_chat,
        name='api-bot-chat'
    ),
    path(
        '<int:pk>/discord/',
        views.discord_connect,
        name='discord-connect'
    ),
]
