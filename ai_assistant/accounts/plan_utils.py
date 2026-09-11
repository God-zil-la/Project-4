from django.conf import settings

from ai_assistant.accounts.models import UserProfile
from ai_assistant.dashboard.cost_utils import (
    calculate_user_current_month_cost,
)


def get_plan_config(profile):
    """
    Return the configured AI limits for the user's plan.
    """
    return settings.AI_PLAN_CONFIG.get(
        profile.effective_plan,
        settings.AI_PLAN_CONFIG[
            UserProfile.PLAN_FREE
        ],
    )


def get_ai_usage_status(user):
    """
    Return the user's current AI usage status.

    This function does not modify usage counters.
    It only determines whether another AI request
    should currently be allowed.
    """
    profile = user.profile
    profile.reset_monthly_count()

    plan_config = get_plan_config(profile)

    monthly_message_limit = plan_config.get(
        "monthly_message_limit"
    )

    monthly_cost_limit = plan_config.get(
        "monthly_cost_limit_usd"
    )

    monthly_usage = (
        calculate_user_current_month_cost(user)
    )

    monthly_cost = monthly_usage["cost_usd"]

    monthly_message_limit_reached = (
        monthly_message_limit is not None
        and profile.monthly_message_count
        >= monthly_message_limit
    )

    monthly_cost_limit_reached = (
        monthly_cost_limit is not None
        and monthly_cost >= monthly_cost_limit
    )

    allowed = not (
        monthly_message_limit_reached
        or monthly_cost_limit_reached
    )

    return {
        "allowed": allowed,
        "plan": profile.effective_plan,
        "monthly_messages_used": (
            profile.monthly_message_count
        ),
        "monthly_message_limit": (
            monthly_message_limit
        ),
        "monthly_cost_usd": monthly_cost,
        "monthly_cost_limit_usd": (
            monthly_cost_limit
        ),
        "monthly_message_limit_reached": (
            monthly_message_limit_reached
        ),
        "monthly_cost_limit_reached": (
            monthly_cost_limit_reached
        ),
    }