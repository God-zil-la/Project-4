"""U6.3-only conservative Free Live Voice eligibility."""

from ai_assistant.accounts.models import UserProfile


class FreeVoiceAccessDenied(Exception):
    """Free Live Voice eligibility cannot be established."""


def require_free_voice_access(*, user):
    """Return a freshly loaded profile only for unambiguous Free accounts.

    No payment provider is called. Uncertain billing state fails closed.
    """
    if (
        user is None
        or not user.is_authenticated
        or not user.is_active
    ):
        raise FreeVoiceAccessDenied("active_authenticated_user_required")

    try:
        profile = UserProfile.objects.get(user_id=user.pk)

        if profile.effective_plan != UserProfile.PLAN_FREE:
            raise FreeVoiceAccessDenied("not_free_plan")

        if profile.plan != UserProfile.PLAN_FREE:
            raise FreeVoiceAccessDenied("stored_plan_not_free")

        if profile.is_subscribed:
            raise FreeVoiceAccessDenied("subscription_flag_present")

        if any((
            profile.stripe_customer_id,
            profile.stripe_subscription_id,
            profile.stripe_subscription_status,
            profile.subscription_current_period_end,
            profile.subscription_ends_at,
            profile.subscription_cancel_at_period_end,
        )):
            raise FreeVoiceAccessDenied("billing_state_requires_verification")

        if profile.has_complimentary_access or profile.has_campaign_access:
            raise FreeVoiceAccessDenied("additional_entitlement_present")

        return profile

    except FreeVoiceAccessDenied:
        raise
    except Exception as exc:
        raise FreeVoiceAccessDenied(
            "free_entitlement_verification_failed"
        ) from exc
