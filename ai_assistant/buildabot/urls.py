"""Root URL configuration for the AI Assistant project."""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from ai_assistant.dashboard import views as dashboard_views
from . import seo

urlpatterns = [
    path('sitemap.xml', seo.sitemap, name='sitemap'),
    path('robots.txt', seo.robots, name='robots'),
path('af47ba2096e54410b397d65549f112d1.txt', seo.indexnow_key, name='indexnow_key'),
    path('delete-account/', TemplateView.as_view(template_name='delete_account.html'), name='delete_account'),
    path('privacy/', TemplateView.as_view(template_name='privacy.html'), name='privacy'),
    path('ai-assistant/', TemplateView.as_view(template_name='seo/ai_assistant.html'), name='ai_assistant'),
    path('ai-chatbot/', TemplateView.as_view(template_name='seo/ai_chatbot.html'), name='ai_chatbot'),
    path('personal-ai-assistant/', TemplateView.as_view(template_name='seo/personal_ai_assistant.html'), name='personal_ai_assistant'),
    path('ai-chatbot-for-business/', TemplateView.as_view(template_name='seo/ai_chatbot_for_business.html'), name='ai_chatbot_for_business'),
    path('website-chatbot/', TemplateView.as_view(template_name='seo/website_chatbot.html'), name='website_chatbot'),
    path('ai-knowledge-base/', TemplateView.as_view(template_name='seo/ai_knowledge_base.html'), name='ai_knowledge_base'),
    path('discord-ai-bot/', TemplateView.as_view(template_name='seo/discord_ai_bot.html'), name='discord_ai_bot'),
    path('ai-assistant-builder/', TemplateView.as_view(template_name='seo/ai_assistant_builder.html'), name='ai_assistant_builder'),
    path('chat-with-pdf/', TemplateView.as_view(template_name='seo/chat_with_pdf.html'), name='chat_with_pdf'),
    path('ai-document-chatbot/', TemplateView.as_view(template_name='seo/ai_document_chatbot.html'), name='ai_document_chatbot'),
    path('ai-tools/', TemplateView.as_view(template_name='seo/ai_tools.html'), name='ai_tools'),
    path('personalized-ai-chatbot/', TemplateView.as_view(template_name='seo/personalized_ai_chatbot.html'), name='personalized_ai_chatbot'),
    path('ai-chatbot-analytics/', TemplateView.as_view(template_name='seo/ai_chatbot_analytics.html'), name='ai_chatbot_analytics'),
    path('ai-assistant-android/', TemplateView.as_view(template_name='seo/ai_assistant_android.html'), name='ai_assistant_android'),
    path('admin/', admin.site.urls),
    path('', dashboard_views.home, name='home'),
    path('dashboard/', include(('ai_assistant.dashboard.urls', 'dashboard'), namespace='dashboard')),
    path('accounts/', include(('ai_assistant.accounts.urls', 'accounts'), namespace='accounts')),
    path('bots/', include(('ai_assistant.bots.urls', 'bots'), namespace='bots')),
    path('payments/', include(('ai_assistant.payments.urls', 'payments'), namespace='payments')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Error handlers
handler400 = "django.views.defaults.bad_request"
handler403 = "django.views.defaults.permission_denied"
handler404 = "django.views.defaults.page_not_found"
handler500 = "django.views.defaults.server_error"

# U6.3 Live Voice API ? local development
from django.urls import include as _u63_include, path as _u63_path

urlpatterns += [
    _u63_path(
        "api/live-voice/",
        _u63_include("ai_assistant.voice.api_urls"),
    ),
]
