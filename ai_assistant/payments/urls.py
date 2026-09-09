from django.urls import path
from .webhooks import stripe_webhook
from .views import (
    CreateCheckoutSessionView,
    billing,
    payment_success,
    payment_cancel,
)

app_name = 'payments'

urlpatterns = [
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
