from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('ai_assistant.dashboard.urls')),
    path('accounts/', include('ai_assistant.accounts.urls', namespace='accounts')),
    path('bots/', include(('ai_assistant.bots.urls', 'bots'), namespace='bots')),
    path('payments/', include('ai_assistant.payments.urls')),
]
