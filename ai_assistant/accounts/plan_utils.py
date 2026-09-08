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
        profile.plan,
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
    profile.reset_daily_count()

    plan_config = get_plan_config(profile)

    daily_limit = plan_config.get(
        "daily_message_limit"
    )

    monthly_cost_limit = plan_config.get(
        "monthly_cost_limit_usd"
    )

    monthly_usage = (
        calculate_user_current_month_cost(user)
    )

    monthly_cost = monthly_usage["cost_usd"]

    daily_limit_reached = (
        daily_limit is not None
        and profile.daily_message_count >= daily_limit
    )

    monthly_cost_limit_reached = (
        monthly_cost_limit is not None
        and monthly_cost >= monthly_cost_limit
    )

    allowed = not (
        daily_limit_reached
        or monthly_cost_limit_reached
    )

    return {
        "allowed": allowed,
        "plan": profile.plan,
        "daily_messages_used": (
            profile.daily_message_count
        ),
        "daily_message_limit": daily_limit,
        "monthly_cost_usd": monthly_cost,
        "monthly_cost_limit_usd": (
            monthly_cost_limit
        ),
        "daily_limit_reached": (
            daily_limit_reached
        ),
        "monthly_cost_limit_reached": (
            monthly_cost_limit_reached
        ),
    }