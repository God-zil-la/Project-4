from .mobile_u5_api import NativeDiscordView, NativeDiscordRevokeView
from .parity_api import DashboardAPIView, AnalyticsAPIView, KnowledgeAPIView, KnowledgeDetailAPIView
from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from . import views, widget_views
from .api_views import (
    BotDetailAPIView,
    BotListCreateAPIView,
    ConversationDetailAPIView,
    ConversationListCreateAPIView,
    api_bot_chat,
)
from .discord_download import download_discord_bridge
from .discord_auth import DiscordIntegrationAuthentication
from .report_api import AIResponseReportAPIView


from . import premium_discord_views
from .premium_discord_interactions import premium_discord_interaction

app_name = "bots"


urlpatterns = [
    path("api/premium-discord/interactions/", premium_discord_interaction, name="premium-discord-interactions"),
    path("api/premium-discord/status/", premium_discord_views.premium_discord_status, name="premium-discord-status"),
    path("api/premium-discord/connect/", premium_discord_views.premium_discord_connect, name="premium-discord-connect"),
    path("api/premium-discord/callback/", premium_discord_views.premium_discord_callback, name="premium-discord-callback"),
    path("api/premium-discord/guilds/connect/", premium_discord_views.premium_discord_add_guild, name="premium-discord-add-guild"),
    path("api/premium-discord/guilds/disconnect/", premium_discord_views.premium_discord_remove_guild, name="premium-discord-remove-guild"),
    path("api/u5/bots/<int:bot_id>/discord/", NativeDiscordView.as_view(), name="native-u5-discord"),
    path("api/u5/bots/<int:bot_id>/discord/<int:integration_id>/revoke/", NativeDiscordRevokeView.as_view(), name="native-u5-discord-revoke"),
    path(
        "api/conversations/<uuid:conversation_id>/messages/<int:message_id>/report/",
        AIResponseReportAPIView.as_view(),
        name="ai-response-report",
    ),
    path("<int:bot_id>/widget/", widget_views.widget_settings, name="widget-settings"),
    path("<int:bot_id>/widget/branding/logo/preview/", widget_views.widget_branding_logo_preview, name="widget-branding-logo-preview"),
    path("api/bots/<int:bot_id>/widget/", widget_views.WidgetSettingsAPI.as_view(), name="widget-settings-api"),
    path("api/bots/<int:bot_id>/widget/branding/", widget_views.WidgetBrandingAPI.as_view(), name="widget-branding-api"),
    path("api/bots/<int:bot_id>/widget/branding/logo/", widget_views.WidgetBrandingLogoAPI.as_view(), name="widget-branding-logo-api"),
    path("public/<uuid:public_id>/", widget_views.public_chat, name="public-chat"),
    path("public/<uuid:public_id>/branding/logo/", widget_views.public_branding_logo, name="public-branding-logo"),
    path("public/<uuid:public_id>/branding/colors.css", widget_views.public_branding_css, name="public-branding-css"),
    path("public/<uuid:public_id>/session/", widget_views.PublicSessionAPI.as_view(), name="public-session"),
    path("public/<uuid:public_id>/message/", widget_views.PublicMessageAPI.as_view(), name="public-message"),
    path("api/dashboard/", DashboardAPIView.as_view(), name="native-dashboard"),
    path("api/analytics/", AnalyticsAPIView.as_view(), name="native-analytics"),
    path("api/bots/<int:bot_id>/knowledge/", KnowledgeAPIView.as_view(), name="native-knowledge"),
    path("api/bots/<int:bot_id>/knowledge/<int:knowledge_id>/", KnowledgeDetailAPIView.as_view(), name="native-knowledge-detail"),
    # Regular views
    path(
        "my-bots/",
        views.my_bots,
        name="my-bots",
    ),
    path(
        "",
        views.bot_list,
        name="list",
    ),
    path(
        "create/",
        views.create_bot,
        name="create",
    ),
    path(
        "<int:bot_id>/edit/",
        views.edit_bot,
        name="edit",
    ),
    path(
        "<int:bot_id>/delete/",
        views.delete_bot,
        name="delete",
    ),
    path(
        "<int:bot_id>/playground/",
        views.bot_chat_playground,
        name="playground",
    ),
    path(
        "<int:bot_id>/knowledge/<int:knowledge_id>/delete/",
        views.delete_knowledge,
        name="delete-knowledge",
    ),
    path(
        "<int:bot_id>/bot_chat_api/",
        views.bot_chat_api,
        name="bot_chat_api",
    ),
    path(
        "<int:bot_id>/ajax_chat/",
        views.ajax_chat,
        name="ajax_chat",
    ),
    path(
        "analytics/",
        views.analytics_dashboard,
        name="analytics",
    ),
    path(
        "admin-dashboard/",
        views.admin_dashboard,
        name="admin-dashboard",
    ),

    # Bot API
    path(
        "api/bots/",
        BotListCreateAPIView.as_view(),
        name="bot-list-create",
    ),
    path(
        "api/bots/<int:pk>/",
        BotDetailAPIView.as_view(),
        name="bot-detail",
    ),

    # Conversation API
    path(
        "api/conversations/",
        ConversationListCreateAPIView.as_view(),
        name="conversation-list-create",
    ),
    path(
        "api/conversations/<uuid:conversation_id>/",
        ConversationDetailAPIView.as_view(),
        name="conversation-detail",
    ),

    # Chat API
    path(
        "api/bot/<int:bot_id>/chat/",
        api_bot_chat,
        name="api-bot-chat",
    ),

    # Authentication API
    path(
        "api/token/",
        obtain_auth_token,
        name="get-user-token",
    ),

    # Discord
    path(
        "<int:bot_id>/discord/integrations/<int:integration_id>/revoke/",
        views.revoke_discord_integration,
        name="discord-revoke",
    ),
    path(
        "api/discord/bot/<int:bot_id>/chat/",
        api_bot_chat.cls.as_view(authentication_classes=[DiscordIntegrationAuthentication]),
        {"require_pro": True},
        name="discord-api-bot-chat",
    ),
    path(
        "<int:bot_id>/discord/setup/",
        views.discord_setup,
        name="discord-setup",
    ),
    path(
        "discord/<int:bot_id>/download/",
        download_discord_bridge,
        name="discord-download",
    ),
]
