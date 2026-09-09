from decimal import Decimal
from urllib.parse import urlsplit

import stripe

from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from ai_assistant.accounts.models import UserProfile
from .pricing import CURRENCY, PLAN_CONFIG


def has_existing_subscription(profile):
    return bool(profile.stripe_subscription_id) and profile.stripe_subscription_status not in {
        "canceled", "incomplete_expired",
    }


@method_decorator(login_required, name="dispatch")
class CreatePortalSessionView(View):
    """Open billing management for the authenticated customer's account."""

    def post(self, request, *args, **kwargs):
        profile = request.user.profile
        if not profile.stripe_customer_id:
            messages.error(request, "No billing account is available to manage.")
            return redirect("payments:billing")
        if not settings.STRIPE_SECRET_KEY:
            messages.error(request, "Billing is temporarily unavailable.")
            return redirect("payments:billing")
        # Resolve the return path locally; never accept a client-supplied URL or customer.
        return_url = request.build_absolute_uri(reverse("payments:billing"))
        try:
            session = stripe.billing_portal.Session.create(
                api_key=settings.STRIPE_SECRET_KEY,
                customer=profile.stripe_customer_id,
                return_url=return_url,
                locale="en",
            )
            destination = urlsplit(session.url)
            if destination.scheme != "https" or destination.netloc != "billing.stripe.com":
                raise ValueError("Invalid billing portal destination.")
        except Exception:
            messages.error(request, "Unable to open subscription management. Please try again later.")
            return redirect("payments:billing")
        response = redirect(session.url)
        response.status_code = 303
        response["Cache-Control"] = "no-store"
        return response


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
            if has_existing_subscription(profile):
                return JsonResponse({"error": "Manage your existing subscription before starting another."}, status=409)
            customer = ({"customer": profile.stripe_customer_id} if profile.stripe_customer_id
                        else {"customer_email": request.user.email})
            checkout_session = stripe.checkout.Session.create(
                api_key=settings.STRIPE_SECRET_KEY,
                **customer,
                mode="subscription",
                locale="en",

                client_reference_id=str(
                    request.user.id
                ),



                line_items=[
                    {
                        "price_data": {
                            "currency": CURRENCY,
                            "unit_amount": plan_config[
                                "unit_amount"
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
    """Render billing actions according to account and configuration state."""
    profile = request.user.profile
    existing_subscription = has_existing_subscription(profile)
    billing_unavailable_reason = ""
    if not settings.STRIPE_SECRET_KEY:
        billing_unavailable_reason = "Billing is not configured in this environment. Please contact support."
    elif existing_subscription and not profile.stripe_customer_id:
        billing_unavailable_reason = "Your existing subscription is missing its billing account link. Please contact support to restore subscription management."
    return render(
        request,
        "payments/billing.html",
        {
            "existing_subscription": existing_subscription,
            "show_management": bool(profile.stripe_customer_id) or existing_subscription,
            "can_manage_subscription": bool(profile.stripe_customer_id and settings.STRIPE_SECRET_KEY),
            "billing_unavailable_reason": billing_unavailable_reason,
            "can_checkout": bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PUBLIC_KEY) and not existing_subscription,
            "STRIPE_PUBLIC_KEY": (
                settings.STRIPE_PUBLIC_KEY
            ),
            "premium_price": Decimal(PLAN_CONFIG[UserProfile.PLAN_PREMIUM]["unit_amount"]) / 100,
            "pro_price": Decimal(PLAN_CONFIG[UserProfile.PLAN_PRO]["unit_amount"]) / 100,
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
