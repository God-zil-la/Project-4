"""U6.3-only authoritative Stripe subscription evidence."""

from datetime import datetime, timezone as utc_timezone

import stripe
from django.conf import settings
from django.utils import timezone

from ai_assistant.accounts.models import UserProfile
from ai_assistant.payments.state import validate_subscription
from ai_assistant.payments.webhooks import get_plan_from_subscription
from ai_assistant.stt.normalizer import ServerPeriodEvidence

from .service import VoiceAccessDenied


def resolve_stripe_voice_evidence(*, user):
    """Resolve fresh Stripe evidence; fail closed on uncertainty."""

    try:
        profile = UserProfile.objects.get(user=user)

        if (
            not profile.stripe_customer_id
            or not profile.stripe_subscription_id
            or not settings.STRIPE_SECRET_KEY
        ):
            raise VoiceAccessDenied(
                "Verified Stripe subscription required."
            )

        subscription = stripe.Subscription.retrieve(
            profile.stripe_subscription_id,
            api_key=settings.STRIPE_SECRET_KEY,
        )

        if subscription.get("id") != profile.stripe_subscription_id:
            raise VoiceAccessDenied(
                "Stripe subscription identity mismatch."
            )

        validate_subscription(profile, subscription)

        if subscription.get("status") != "active":
            raise VoiceAccessDenied(
                "Active Stripe subscription required."
            )

        plan = get_plan_from_subscription(subscription)

        if plan not in {
            UserProfile.PLAN_PREMIUM,
            UserProfile.PLAN_PRO,
        }:
            raise VoiceAccessDenied(
                "Premium or Pro monthly subscription required."
            )

        items = subscription.get("items", {}).get("data", [])

        if len(items) != 1:
            raise VoiceAccessDenied(
                "Unambiguous Stripe billing period required."
            )

        item = items[0]

        subscription_start = subscription.get("current_period_start")
        subscription_end = subscription.get("current_period_end")
        item_start = item.get("current_period_start")
        item_end = item.get("current_period_end")

        if (
            subscription_start is not None
            and item_start is not None
            and subscription_start != item_start
        ):
            raise VoiceAccessDenied(
                "Conflicting Stripe period start."
            )

        if (
            subscription_end is not None
            and item_end is not None
            and subscription_end != item_end
        ):
            raise VoiceAccessDenied(
                "Conflicting Stripe period end."
            )

        start = (
            subscription_start
            if subscription_start is not None
            else item_start
        )
        end = (
            subscription_end
            if subscription_end is not None
            else item_end
        )

        if not isinstance(item.get("id"), str) or not item["id"]:
            raise VoiceAccessDenied(
                "Stripe subscription item identity required."
            )

        if (
            type(start) is not int
            or type(end) is not int
            or start <= 0
            or end <= start
        ):
            raise VoiceAccessDenied(
                "Verified Stripe billing period unavailable."
            )

        starts_at = datetime.fromtimestamp(
            start, tz=utc_timezone.utc
        )
        ends_at = datetime.fromtimestamp(
            end, tz=utc_timezone.utc
        )
        verified_at = timezone.now().astimezone(
            utc_timezone.utc
        )

        if not starts_at <= verified_at < ends_at:
            raise VoiceAccessDenied(
                "Stripe subscription period is not current."
            )

        return ServerPeriodEvidence(
            user_id=user.pk,
            provider="stripe",
            environment=(
                "production"
                if subscription.get("livemode") is True
                else "sandbox"
            ),
            subscription_id=subscription["id"],
            cycle_id=f"{subscription['id']}:{start}:{end}",
            plan=plan,
            starts_at=starts_at,
            ends_at=ends_at,
            verified_at=verified_at,
            entitlement_active=True,
            verification_succeeded=True,
            category="ordinary_monthly",
        )

    except VoiceAccessDenied:
        raise
    except Exception as exc:
        raise VoiceAccessDenied(
            "Stripe voice entitlement verification failed."
        ) from exc
