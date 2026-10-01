from django.urls import path
from .webhooks import stripe_webhook
from .views import (
    CreateCheckoutSessionView,
    CreatePortalSessionView,
    UpgradeSubscriptionView,
    ResumeSubscriptionView,
    KeepSubscriptionView,
    DowngradeSubscriptionView,
    RecoverSubscriptionView,
    billing,
    payment_success,
    payment_cancel,
)

from .store_api import StoreCatalog, StoreIntent, StoreVerify, StoreStatus
from .store_notifications import apple_notification, google_notification

app_name = 'payments'

urlpatterns = [
    path('api/store/catalog/', StoreCatalog.as_view(), name='store_catalog'),
    path('api/store/intent/', StoreIntent.as_view(), name='store_intent'),
    path('api/store/verify/', StoreVerify.as_view(), name='store_verify'),
    path('api/store/status/', StoreStatus.as_view(), name='store_status'),
    path('notifications/apple/', apple_notification, name='apple_notification'),
    path('notifications/google/', google_notification, name='google_notification'),
    path("keep/", KeepSubscriptionView.as_view(), name="keep_subscription"),
    path("resume/", ResumeSubscriptionView.as_view(), name="resume_subscription"),
    path("downgrade/", DowngradeSubscriptionView.as_view(), name="downgrade_subscription"),
    path('recover/', RecoverSubscriptionView.as_view(), name='recover_subscription'),
    path('upgrade/', UpgradeSubscriptionView.as_view(), name='upgrade_subscription'),
    path('create-portal-session/', CreatePortalSessionView.as_view(), name='create_portal_session'),
    path('webhook/', stripe_webhook, name='webhook'),
    path('', billing, name='billing'),
    path(
        'create-checkout-session/',
        CreateCheckoutSessionView.as_view(),
        name='create_checkout_session',
    ),
    path('success/', payment_success, name='payment_success'),
    path('cancel/', payment_cancel, name='payment_cancel'),
]
