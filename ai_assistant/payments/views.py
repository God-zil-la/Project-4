from decimal import Decimal
from urllib.parse import urlsplit
from uuid import uuid4
from hashlib import sha256
import logging

import stripe

from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
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
from .models import CheckoutAttempt, SubscriptionRecovery, SubscriptionChange
from .state import (has_existing_subscription, reconcile_customer, clear_subscription,
                    validate_subscription, TERMINAL)
from .webhooks import get_plan_from_subscription, update_profile_from_subscription
from .recovery import recovery_reason, recovery_source, replacement_parameters, run_replacement

logger = logging.getLogger(__name__)


def log_change_failure(action, stage, error):
    """Never log exception messages, provider payloads, or credentials."""
    from .changes import ChangeBlocked
    reason = error.reason if isinstance(error, ChangeBlocked) else "unexpected_failure"
    # A code location distinguishes other guards and storage/provider failures
    # without serializing exception text or traceback locals.
    origin = "unknown"
    trace = error.__traceback__
    while trace:
        module = trace.tb_frame.f_globals.get("__name__", "")
        if module.startswith("ai_assistant.payments."):
            origin = "%s:%s" % (module, trace.tb_lineno)
        trace = trace.tb_next
    logger.warning("Subscription change blocked action=%s stage=%s reason=%s error_type=%s origin=%s",
                   action, stage, reason, type(error).__name__, origin)


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
@method_decorator(never_cache, name="dispatch")
class RecoverSubscriptionView(View):
    """Recover legacy test prices with an owned change or durable replacement."""

    def post(self, request):
        try:
            if not settings.STRIPE_SECRET_KEY:
                raise ValueError("Billing unavailable")
            intent = signing.loads(request.POST.get("recovery_token", ""),
                                   salt="billing-recovery", max_age=3600)
            target = intent.get("plan")
            if intent.get("user") != request.user.pk or target not in PLAN_CONFIG:
                raise ValueError("Invalid recovery owner or plan")
            # Persist cross-currency intent before any irreversible provider call.
            with transaction.atomic():
                profile = UserProfile.objects.select_for_update().get(user=request.user)
                attempt = SubscriptionRecovery.objects.filter(profile=profile).first()
                if attempt:
                    if attempt.plan != target or attempt.source_subscription != intent.get("subscription"):
                        raise ValueError("A different migration already exists")
                    if attempt.completed:
                        messages.info(request, "This migration is already complete. Refresh Billing to view your current plan.")
                        return redirect("payments:billing")
                else:
                    reconcile_customer(profile)
                    if profile.stripe_subscription_id != intent.get("subscription"):
                        raise ValueError("Subscription changed")
                    subscription = owned_subscription(profile)
                    if (get_plan_from_subscription(subscription) == "free"
                            and recovery_reason(subscription)[1]
                            and subscription["items"]["data"][0]["price"]["currency"] == "sek"):
                        if any(intent.get(key) != value for key, value in recovery_source(subscription).items()):
                            raise ValueError("Source price changed")
                        attempt = SubscriptionRecovery.objects.create(profile=profile,
                            source_subscription=subscription["id"], plan=target,
                            source=recovery_source(subscription),
                            parameters=replacement_parameters(subscription, profile, target))
            if attempt:
                with transaction.atomic():
                    profile = UserProfile.objects.select_for_update().get(user=request.user)
                    attempt = SubscriptionRecovery.objects.get(profile=profile)
                    if not attempt.completed:
                        run_replacement(profile, attempt)
                messages.success(request, "Your legacy Test Mode subscription has been replaced with the selected USD plan. No overlapping subscription was created.")
                return redirect("payments:billing")
            with transaction.atomic():
                profile = UserProfile.objects.select_for_update().get(user=request.user)
                reconcile_customer(profile)
                if profile.stripe_subscription_id != intent.get("subscription"):
                    raise ValueError("Subscription changed")
                subscription = owned_subscription(profile)
                update_profile_from_subscription(profile, subscription)
                if get_plan_from_subscription(subscription) in PLAN_CONFIG:
                    messages.info(request, "This subscription already has a current plan. Review Billing before making another change.")
                    return redirect("payments:billing")
                if (not recovery_reason(subscription)[1]
                        or subscription["items"]["data"][0]["price"]["currency"] != CURRENCY):
                    raise ValueError("Subscription requires management")
                source = recovery_source(subscription)
                if any(intent.get(key) != value for key, value in source.items()):
                    raise ValueError("Subscription item changed; refresh Billing")
                product = stripe.Product.create(api_key=settings.STRIPE_SECRET_KEY,
                    name=PLAN_CONFIG[target]["name"],
                    idempotency_key="ai-assistant-recovery-product-v1-" + target)
                # The key identifies the source item/price and destination, not the
                # browser form, so separate tabs retry the identical operation.
                key = "|".join([str(request.user.pk), *source.values(), target])
                stripe.Subscription.modify(subscription["id"], api_key=settings.STRIPE_SECRET_KEY,
                    items=[{"id": source["item"], "quantity": 1, "price_data": {
                        "currency": CURRENCY, "unit_amount": PLAN_CONFIG[target]["unit_amount"],
                        "recurring": {"interval": "month"}, "product": product.id}}],
                    proration_behavior="always_invoice", payment_behavior="error_if_incomplete",
                    billing_cycle_anchor="unchanged",
                    metadata={"plan": target, "user_id": str(request.user.pk)},
                    idempotency_key="recover-" + sha256(key.encode()).hexdigest())
                current = owned_subscription(profile)
                update_profile_from_subscription(profile, current)
                if profile.has_paid_plan and profile.plan == target:
                    messages.success(request, "Your existing subscription now uses the selected USD plan. Your renewal date and any scheduled cancellation are unchanged.")
                else:
                    messages.info(request, "The change is being confirmed. Refresh billing status before trying again.")
        except signing.BadSignature:
            messages.error(request, "This recovery form has expired or is invalid. Refresh Billing and try again.")
        except stripe.error.CardError:
            messages.error(request, "Payment could not be completed. Open Manage subscription to resolve payment before trying again.")
        except Exception:
            messages.error(request, "Unable to confirm the plan change. Refresh billing status or contact support. No additional checkout has been started.")
        return redirect("payments:billing")


@method_decorator(login_required, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class ChangeSubscriptionView(View):
    """Commit owner consent before provider calls; retain uncertain operations."""
    action = "resume"

    def post(self, request):
        from .changes import eligible, inventory, run_change
        stage = "owner_intent"
        try:
            if not settings.STRIPE_SECRET_KEY:
                raise ValueError("Billing unavailable")
            intent = signing.loads(request.POST.get("change_token", ""),
                                   salt="billing-change", max_age=3600)
            if intent.get("user") != request.user.pk or intent.get("action") != self.action:
                raise ValueError("Invalid owner intent")
            with transaction.atomic():
                profile = UserProfile.objects.select_for_update().get(user=request.user)
                if intent.get("subscription") != profile.stripe_subscription_id or not profile.stripe_customer_id:
                    raise ValueError("Subscription changed")
                stage = "authoritative_subscription"
                subscription = owned_subscription(profile)
                update_profile_from_subscription(profile, subscription)
                change = SubscriptionChange.objects.filter(profile=profile).first()
                if change and str(change.key) == intent.get("retry"):
                    if change.action != self.action:
                        raise ValueError("Conflicting action")
                elif change and change.status not in {"complete", "removed", "failed"}:
                    raise ValueError("Resolve the saved change before choosing another action")
                else:
                    stage = "eligibility"
                    source = eligible(subscription)
                    stage = "consent_terms"
                    if (intent.get("plan") != source["plan"] or intent.get("end") != source["end"]
                            or intent.get("canceled") != bool(subscription.get("cancel_at_period_end"))):
                        raise ValueError("Terms changed; refresh Billing")
                    if self.action == "upgrade" and source["plan"] != "premium":
                        raise ValueError("Upgrade requires Premium")
                    if self.action == "downgrade" and source["plan"] != "pro":
                        raise ValueError("Downgrade requires Pro")
                    if self.action == "resume" and not subscription.get("cancel_at_period_end"):
                        messages.info(request, "Your subscription already renews normally.")
                        return redirect("payments:billing")
                    stage = "inventory"
                    inventory(profile, subscription)
                    stage = "save_intent"
                    if change:
                        change.delete()
                    change = SubscriptionChange.objects.create(profile=profile, action=self.action, source=source)
                expected_key = change.key
            # Catch inside the transaction so saved retry stages survive failures.
            with transaction.atomic():
                profile = UserProfile.objects.select_for_update().get(user=request.user)
                change = SubscriptionChange.objects.get(profile=profile)
                if change.key != expected_key or change.action != self.action:
                    raise ValueError("Another operation replaced this intent")
                try:
                    stage = "execute_saved_change"
                    current = owned_subscription(profile)
                    update_profile_from_subscription(profile, current)
                    change.refresh_from_db()
                    run_change(profile, change, current)
                    current = owned_subscription(profile)
                    update_profile_from_subscription(profile, current)
                    change.refresh_from_db()
                    if change.status == "complete":
                        messages.success(request, "Your subscription continues on " + profile.plan.title() + ". Your renewal date is unchanged and scheduled cancellation is cleared.")
                    elif change.status == "scheduled":
                        messages.success(request, "Premium is scheduled for your next renewal. Pro remains your current plan until then. Your subscription will continue renewing.")
                    else:
                        messages.info(request, "Your change needs confirmation. Refresh Billing or retry the saved change. Contact support if it remains unresolved.")
                except stripe.error.CardError:
                    messages.error(request, "Payment could not be completed. The upgrade was not applied. Manage subscription to resolve payment, then choose Upgrade to Pro again from Billing.")
                except Exception as error:
                    log_change_failure(self.action, stage, error)
                    messages.error(request, "Unable to confirm the change. Cancellation may already have been cleared. Refresh Billing, retry the saved change, or contact support before making another change.")
        except signing.BadSignature:
            messages.error(request, "This form has expired or is invalid. Refresh Billing and try again.")
        except Exception as error:
            log_change_failure(self.action, stage, error)
            messages.error(request, "This change cannot be safely applied. Refresh Billing, resolve payment in Manage subscription, or contact support.")
        return redirect("payments:billing")


class UpgradeSubscriptionView(ChangeSubscriptionView):
    action = "upgrade"


class ResumeSubscriptionView(ChangeSubscriptionView):
    action = "resume"


class DowngradeSubscriptionView(ChangeSubscriptionView):
    action = "downgrade"


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
@method_decorator(never_cache, name="dispatch")
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
            # Commit the intent before provider calls so an uncertain response can
            # only retry the same request, including after a worker restart.
            with transaction.atomic():
                profile = UserProfile.objects.select_for_update().get(user=request.user)
                if SubscriptionChange.objects.filter(profile=profile).exclude(status__in=["complete", "removed", "failed"]).exists():
                    return JsonResponse({"error": "Resolve your saved subscription change before starting checkout."}, status=409)
                if SubscriptionRecovery.objects.filter(profile=profile, completed=False).exists():
                    return JsonResponse({"error": "Finish the pending subscription migration from Billing before starting checkout."}, status=409)
                if profile.stripe_subscription_id and not profile.stripe_customer_id:
                    return JsonResponse({"error": "Contact support to restore your billing account link."}, status=409)
                reconcile_customer(profile)
                if has_existing_subscription(profile):
                    return JsonResponse({"error": "Manage your existing subscription before starting another."}, status=409)
                attempt, _ = CheckoutAttempt.objects.get_or_create(profile=profile, defaults={
                    "plan": plan,
                    "success_url": request.build_absolute_uri("/payments/success/") + "?session_id={CHECKOUT_SESSION_ID}",
                    "cancel_url": request.build_absolute_uri("/payments/cancel/"),
                })
            with transaction.atomic():
                profile = UserProfile.objects.select_for_update().get(user=request.user)
                attempt = CheckoutAttempt.objects.get(profile=profile)
                if SubscriptionChange.objects.filter(profile=profile).exclude(status__in=["complete", "removed", "failed"]).exists():
                    return JsonResponse({"error": "Resolve your saved subscription change before starting checkout."}, status=409)
                if SubscriptionRecovery.objects.filter(profile=profile, completed=False).exists():
                    return JsonResponse({"error": "Finish the pending subscription migration from Billing before starting checkout."}, status=409)
                if profile.stripe_subscription_id and not profile.stripe_customer_id:
                    return JsonResponse({"error": "Contact support to restore your billing account link."}, status=409)
                reconcile_customer(profile)
                if has_existing_subscription(profile):
                    return JsonResponse({"error": "Manage your existing subscription before starting another."}, status=409)
                if attempt.session_id:
                    session = stripe.checkout.Session.retrieve(attempt.session_id, api_key=settings.STRIPE_SECRET_KEY)
                    if (session.get("id") != attempt.session_id
                            or session.get("customer") != profile.stripe_customer_id):
                        raise ValueError("Checkout customer mismatch")
                    if session.get("status") == "expired":
                        attempt.delete()
                        return JsonResponse({"error": "Your previous checkout expired. Choose a plan again."}, status=409)
                    if session.get("status") == "complete":
                        subscription = stripe.Subscription.retrieve(session.get("subscription"), api_key=settings.STRIPE_SECRET_KEY)
                        validate_subscription(profile, subscription)
                        if subscription.get("id") != session.get("subscription"):
                            raise ValueError("Checkout subscription mismatch")
                        if subscription.get("status") in TERMINAL:
                            attempt.delete()
                            return JsonResponse({"error": "Your previous subscription ended. Choose a plan again."}, status=409)
                        return JsonResponse({"error": "Your payment is being confirmed. Refresh billing status."}, status=409)
                    if session.get("status") != "open":
                        raise ValueError("Unknown checkout status")
                    if attempt.plan != plan:
                        return JsonResponse({"error": "Another plan checkout is open. Complete it or let it expire before changing plans."}, status=409)
                    return JsonResponse({"id": attempt.session_id, "plan": attempt.plan})
                if timezone.now() - attempt.started_at > timedelta(hours=23):
                    return JsonResponse({"error": "Checkout confirmation requires support. No new payment has been started."}, status=409)
                if attempt.plan != plan:
                    return JsonResponse({"error": "Retry your original plan to confirm the pending checkout before changing plans."}, status=409)
                if not profile.stripe_customer_id:
                    customer = stripe.Customer.create(api_key=settings.STRIPE_SECRET_KEY,
                        metadata={"user_id": str(request.user.pk)},
                        idempotency_key="checkout-customer-" + str(attempt.key))
                    profile.stripe_customer_id = customer.id
                    profile.save(update_fields=["stripe_customer_id"])
                # Include old sessions created before durable intents were introduced.
                sessions = stripe.checkout.Session.list(customer=profile.stripe_customer_id,
                    limit=100, api_key=settings.STRIPE_SECRET_KEY)
                sessions = list(sessions.auto_paging_iter())
                recovered = next((s for s in sessions if
                    (s.get("metadata") or {}).get("attempt") == str(attempt.key)), None)
                if recovered:
                    attempt.session_id = recovered["id"]
                    attempt.save(update_fields=["session_id"])
                    return JsonResponse({"error": "Previous checkout recovered. Choose your plan again to continue."}, status=409)
                if any(session.get("mode") == "subscription" and session.get("status") == "open" for session in sessions):
                    return JsonResponse({"error": "An existing checkout is open. Complete it or let it expire before starting another."}, status=409)
                customer = {"customer": profile.stripe_customer_id}
                checkout_session = stripe.checkout.Session.create(
                    api_key=settings.STRIPE_SECRET_KEY,
                    idempotency_key="checkout-" + str(attempt.key),
                    expires_at=int(attempt.started_at.timestamp()) + 86400,
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
                        "attempt": str(attempt.key),
                        "plan": plan,
                        "user_id": str(
                            request.user.id
                        ),
                    },

                    success_url=attempt.success_url,
                    cancel_url=attempt.cancel_url,
                )
                attempt.session_id = checkout_session.id
                attempt.save(update_fields=["session_id"])

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
    refresh_failed = False
    recovery_message = ""
    recovery_options = []
    recovery_replacement = False
    contradictory = ((profile.plan == UserProfile.PLAN_FREE and
        (profile.subscription_cancel_at_period_end or profile.subscription_ends_at
            or profile.stripe_subscription_status in {"active", "trialing"}))
        or (profile.stripe_customer_id and not profile.stripe_subscription_id)
        or (profile.stripe_subscription_status in TERMINAL and
            (profile.plan != UserProfile.PLAN_FREE or profile.is_subscribed
             or profile.subscription_cancel_at_period_end))
        or (profile.subscription_ends_at and profile.subscription_ends_at <= timezone.now()
            and has_existing_subscription(profile)))
    if settings.STRIPE_SECRET_KEY and (request.GET.get("sync") == "1" or contradictory):
        try:
            with transaction.atomic():
                profile = UserProfile.objects.select_for_update().get(user=request.user)
                selected = reconcile_customer(profile)
                if profile.stripe_subscription_status == "active" and profile.plan == UserProfile.PLAN_FREE:
                    subscription = (owned_subscription(profile)
                        if (selected.get("items") or {}).get("data") else selected)
                    update_profile_from_subscription(profile, subscription)
                    recovery_message, eligible = recovery_reason(subscription)
                    if eligible:
                        recovery_replacement = subscription["items"]["data"][0]["price"]["currency"] == "sek"
                        recovery_options = [{"plan": plan, "name": plan.title(),
                            "token": signing.dumps({"user": request.user.pk, "plan": plan,
                                **recovery_source(subscription)}, salt="billing-recovery")}
                            for plan in PLAN_CONFIG]
        except Exception:
            refresh_failed = True
            profile.refresh_from_db()
            messages.error(request, "Billing status could not be refreshed. Showing the last confirmed status; please try again shortly.")
    elif not profile.stripe_subscription_id and not profile.stripe_customer_id:
        with transaction.atomic():
            profile = UserProfile.objects.select_for_update().get(user=request.user)
            clear_subscription(profile)
    existing_subscription = has_existing_subscription(profile)
    pending_recovery = SubscriptionRecovery.objects.filter(profile=profile, completed=False).first()
    if pending_recovery:
        recovery_replacement = True
        recovery_message = "Your Test Mode subscription migration needs confirmation. Resume the saved migration below. If it cannot complete, contact support; do not start another checkout."
        recovery_options = [{"plan": pending_recovery.plan, "name": pending_recovery.plan.title(),
            "token": signing.dumps({"user": request.user.pk, "plan": pending_recovery.plan,
                "subscription": pending_recovery.source_subscription}, salt="billing-recovery")}]
    billing_unavailable_reason = ""
    if not settings.STRIPE_SECRET_KEY:
        billing_unavailable_reason = "Billing is not configured in this environment. Please contact support."
    elif existing_subscription and not profile.stripe_customer_id:
        billing_unavailable_reason = "Your existing subscription is missing its billing account link. Please contact support to restore subscription management."
    elif refresh_failed:
        billing_unavailable_reason = "Confirm billing status before starting a payment. Refresh this page or contact support if the problem continues."
    change = SubscriptionChange.objects.filter(profile=profile).first()
    changing = bool(change and change.status not in {"complete", "removed", "failed"})
    can_change = bool(settings.STRIPE_SECRET_KEY and profile.stripe_customer_id
        and not refresh_failed and not pending_recovery and existing_subscription
        and profile.has_paid_plan and profile.stripe_subscription_status == "active")
    def change_token(action):
        return signing.dumps({"user": request.user.pk, "action": action,
            "subscription": profile.stripe_subscription_id, "plan": profile.plan,
            "end": int(profile.subscription_current_period_end.timestamp()) if profile.subscription_current_period_end else None,
            "canceled": profile.subscription_cancel_at_period_end, "nonce": uuid4().hex,
            "retry": str(change.key) if changing and change.action == action else ""}, salt="billing-change")
    return render(
        request,
        "payments/billing.html",
        {
            "existing_subscription": existing_subscription,
            "recovery_message": recovery_message,
            "recovery_options": recovery_options,
            "recovery_replacement": recovery_replacement,
            "billing_profile": profile,
            "current_plan": dict(UserProfile.PLAN_CHOICES)[profile.effective_plan],
            "has_paid_access": profile.has_paid_plan,
            "can_upgrade": can_change and not changing and profile.is_premium,
            "can_resume": can_change and not changing and profile.subscription_cancel_at_period_end,
            "can_downgrade": can_change and not changing and profile.is_pro,
            "upgrade_token": change_token("upgrade"),
            "resume_token": change_token("resume"),
            "downgrade_token": change_token("downgrade"),
            "subscription_change": change if changing else None,
            "change_effective_date": timezone.datetime.fromtimestamp(change.source["end"], tz=timezone.get_current_timezone()) if changing else None,
            "retry_token": change_token(change.action) if changing else "",
            "retry_url": reverse("payments:" + change.action + "_subscription") if changing else "",
            "show_management": bool(profile.stripe_customer_id) or existing_subscription,
            "can_manage_subscription": bool(profile.stripe_customer_id and settings.STRIPE_SECRET_KEY),
            "billing_unavailable_reason": billing_unavailable_reason,
            "can_checkout": bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PUBLIC_KEY) and not existing_subscription and not refresh_failed and not pending_recovery and not changing,
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
