from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from ai_assistant.dashboard import views as dashboard_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include(('ai_assistant.dashboard.urls', 'dashboard'), namespace='dashboard')),
    path('accounts/', include(('ai_assistant.accounts.urls', 'accounts'), namespace='accounts')),
    path('bots/', include(('ai_assistant.bots.urls', 'bots'), namespace='bots')),
    path('payments/', include(('ai_assistant.payments.urls', 'payments'), namespace='payments')),
    path('', dashboard_views.home, name='home'),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
