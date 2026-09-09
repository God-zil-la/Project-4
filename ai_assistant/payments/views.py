from decimal import Decimal
from urllib.parse import urlsplit
from uuid import uuid4
from hashlib import sha256

import stripe

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.views import View
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from ai_assistant.accounts.models import UserProfile
from .pricing import CURRENCY, PLAN_CONFIG
from .webhooks import get_plan_from_subscription, update_profile_from_subscription


def owned_subscription(profile):
    subscription = stripe.Subscription.retrieve(
        profile.stripe_subscription_id, api_key=settings.STRIPE_SECRET_KEY,
        expand=["latest_invoice"])
    owner = (subscription.get("metadata") or {}).get("user_id")
    if (subscription.get("id") != profile.stripe_subscription_id
            or subscription.get("customer") != profile.stripe_customer_id
            or (owner and str(owner) != str(profile.user_id))
            or subscription.get("livemode") is not settings.STRIPE_SECRET_KEY.startswith(("sk_live_", "rk_live_"))):
        raise ValueError("Subscription ownership or mode mismatch")
    return subscription


@method_decorator(login_required, name="dispatch")
class UpgradeSubscriptionView(View):
    """Replace one owned monthly item; never create a second subscription."""

    def post(self, request):
        if not settings.STRIPE_SECRET_KEY:
            messages.error(request, "Billing is temporarily unavailable.")
            return redirect("payments:billing")
        try:
            token = request.POST.get("upgrade_token", "")
            intent = signing.loads(token, salt="billing-upgrade", max_age=3600)
            with transaction.atomic():
                profile = UserProfile.objects.select_for_update().get(user=request.user)
                if (intent.get("user") != request.user.pk
                        or intent.get("subscription") != profile.stripe_subscription_id
                        or not profile.stripe_customer_id or not has_existing_subscription(profile)):
                    raise ValueError("Invalid upgrade owner")
                subscription = owned_subscription(profile)
                plan = get_plan_from_subscription(subscription)
                if plan == UserProfile.PLAN_PRO:
                    update_profile_from_subscription(profile, subscription)
                    messages.info(request, "Your subscription is already on Pro.")
                    return redirect("payments:billing")
                if (plan != UserProfile.PLAN_PREMIUM or subscription.get("status") != "active"
                        or subscription.get("collection_method") != "charge_automatically"
                        or subscription.get("pending_update") or subscription.get("schedule")
                        or subscription.get("pause_collection")):
                    raise ValueError("Subscription is not eligible for immediate upgrade")
                invoice = subscription.get("latest_invoice")
                if not isinstance(invoice, dict) or invoice.get("status") != "paid":
                    # Do not credit unused Premium time that has not been paid for.
                    raise ValueError("Latest subscription invoice is not paid")
                item = subscription["items"]["data"][0]
                if not item.get("id"):
                    raise ValueError("Missing subscription item")
                # Separate product keeps Stripe invoices accurate even though checkout
                # originally created an inline Premium price/product.
                product = stripe.Product.create(
                    api_key=settings.STRIPE_SECRET_KEY,
                    name=PLAN_CONFIG[UserProfile.PLAN_PRO]["name"],
                    idempotency_key="ai-assistant-pro-product-v1")
                stripe.Subscription.modify(
                    subscription["id"], api_key=settings.STRIPE_SECRET_KEY,
                    items=[{"id": item["id"], "quantity": 1, "price_data": {
                        "currency": CURRENCY, "unit_amount": PLAN_CONFIG[UserProfile.PLAN_PRO]["unit_amount"],
                        "recurring": {"interval": "month"}, "product": product.id}}],
                    proration_behavior="always_invoice", payment_behavior="error_if_incomplete",
                    billing_cycle_anchor="unchanged",
                    metadata={"plan": UserProfile.PLAN_PRO, "user_id": str(request.user.pk)},
                    idempotency_key="upgrade-" + sha256(token.encode()).hexdigest(),
                )
                # Retrieve under the same lock used by webhooks, including on retries.
                current = owned_subscription(profile)
                update_profile_from_subscription(profile, current)
                if profile.plan == UserProfile.PLAN_PRO:
                    messages.success(request, "You are now on Pro. Your renewal date and any scheduled cancellation are unchanged.")
                else:
                    messages.info(request, "Your upgrade is being confirmed. Refresh billing status shortly.")
        except stripe.error.CardError:
            messages.error(request, "Payment could not be completed. Premium has not been upgraded. Open Manage subscription to update your payment method, then try again. If your bank requires authentication, contact support.")
        except signing.BadSignature:
            messages.error(request, "This upgrade form has expired or is invalid. Please try again from Billing.")
        except Exception:
            messages.error(request, "Unable to confirm the upgrade. Refresh billing status before trying again, or contact support.")
        response = redirect("payments:billing")
        response["Cache-Control"] = "no-store"
        return response


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
        return_url = request.build_absolute_uri(reverse("payments:billing")) + "?sync=1"
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
@require_GET
@never_cache
def billing(request):
    """Render billing actions according to account and configuration state."""
    profile = request.user.profile
    if request.GET.get("sync") == "1" and profile.stripe_subscription_id and profile.stripe_customer_id and settings.STRIPE_SECRET_KEY:
        try:
            with transaction.atomic():
                profile = UserProfile.objects.select_for_update().get(user=request.user)
                update_profile_from_subscription(profile, owned_subscription(profile))
        except Exception:
            messages.error(request, "Billing status could not be refreshed. Showing the last confirmed status; please try again shortly.")
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
            "billing_profile": profile,
            "can_upgrade": bool(settings.STRIPE_SECRET_KEY and profile.stripe_customer_id
                and existing_subscription and profile.plan == UserProfile.PLAN_PREMIUM
                and profile.stripe_subscription_status == "active"),
            "upgrade_token": signing.dumps({"user": request.user.pk,
                "subscription": profile.stripe_subscription_id, "nonce": uuid4().hex}, salt="billing-upgrade"),
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
