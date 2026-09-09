import stripe

from django.conf import settings
from django.shortcuts import render
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from ai_assistant.accounts.models import UserProfile


PLAN_CONFIG = {
    UserProfile.PLAN_PREMIUM: {
        "name": "AI Assistant Premium",
        "price_sek": 12900,
    },
    UserProfile.PLAN_PRO: {
        "name": "AI Assistant Pro",
        "price_sek": 24900,
    },
}


@method_decorator(login_required, name="dispatch")
class CreateCheckoutSessionView(View):
    """Create a Stripe Checkout session for a paid monthly plan."""

    def post(self, request, *args, **kwargs):
        try:
            plan = request.POST.get(
                "plan",
                UserProfile.PLAN_PREMIUM,
            )

            plan_config = PLAN_CONFIG.get(plan)

            if not plan_config:
                return JsonResponse(
                    {
                        "error": "Invalid subscription plan.",
                    },
                    status=400,
                )

            if not settings.STRIPE_SECRET_KEY:
                return JsonResponse({"error": "Billing is temporarily unavailable."}, status=503)
            profile = request.user.profile
            if profile.stripe_subscription_id and profile.stripe_subscription_status not in {"canceled", "incomplete_expired"}:
                return JsonResponse({"error": "Manage your existing subscription before starting another."}, status=409)
            customer = ({"customer": profile.stripe_customer_id} if profile.stripe_customer_id
                        else {"customer_email": request.user.email})
            checkout_session = stripe.checkout.Session.create(
                api_key=settings.STRIPE_SECRET_KEY,
                **customer,
                mode="subscription",

                client_reference_id=str(
                    request.user.id
                ),



                line_items=[
                    {
                        "price_data": {
                            "currency": "sek",
                            "unit_amount": plan_config[
                                "price_sek"
                            ],
                            "recurring": {
                                "interval": "month",
                            },
                            "product_data": {
                                "name": plan_config[
                                    "name"
                                ],
                            },
                        },
                        "quantity": 1,
                    },
                ],

                subscription_data={
                    "metadata": {
                        "plan": plan,
                        "user_id": str(
                            request.user.id
                        ),
                    },
                },

                metadata={
                    "plan": plan,
                    "user_id": str(
                        request.user.id
                    ),
                },

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
                    "plan": plan,
                }
            )

        except Exception:
            return JsonResponse(
                {
                    "error": "Unable to start checkout. Please try again later.",
                },
                status=500,
            )


@login_required
def billing(request):
    """Render the billing page with Stripe configuration."""
    return render(
        request,
        "payments/billing.html",
        {
            "STRIPE_PUBLIC_KEY": (
                settings.STRIPE_PUBLIC_KEY
            ),
            "premium_price": 129,
            "pro_price": 249,
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