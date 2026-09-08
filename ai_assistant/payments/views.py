import stripe

from django.conf import settings
from django.shortcuts import render
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator


stripe.api_key = settings.STRIPE_SECRET_KEY


@method_decorator(login_required, name="dispatch")
class CreateCheckoutSessionView(View):
    """Create a Stripe Checkout session for the Premium monthly plan."""

    def post(self, request, *args, **kwargs):
        try:
            checkout_session = stripe.checkout.Session.create(
                mode="subscription",

                client_reference_id=str(request.user.id),

                customer_email=request.user.email,

                line_items=[
                    {
                        "price_data": {
                            "currency": "sek",
                            "unit_amount": 12900,
                            "recurring": {
                                "interval": "month",
                            },
                            "product_data": {
                                "name": "AI Assistant Premium",
                            },
                        },
                        "quantity": 1,
                    },
                ],

                success_url=request.build_absolute_uri(
                    "/payments/success/"
                )
                + "?session_id={CHECKOUT_SESSION_ID}",

                cancel_url=request.build_absolute_uri(
                    "/payments/cancel/"
                ),
            )

            return JsonResponse(
                {
                    "id": checkout_session.id,
                }
            )

        except Exception as error:
            return JsonResponse(
                {
                    "error": str(error),
                },
                status=500,
            )


@login_required
def billing(request):
    """Render the billing page with the Stripe public key."""

    return render(
        request,
        "payments/billing.html",
        {
            "STRIPE_PUBLIC_KEY": settings.STRIPE_PUBLIC_KEY,
        },
    )


@login_required
def payment_success(request):
    """Render the payment success page."""

    return render(
        request,
        "payments/success.html",
    )


@login_required
def payment_cancel(request):
    """Render the payment cancellation page."""

    return render(
        request,
        "payments/cancel.html",
    )