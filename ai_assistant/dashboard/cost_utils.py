from datetime import datetime, timezone as dt_timezone

from django.conf import settings

from ai_assistant.dashboard.models import BotUsageLog


def calculate_ai_cost(
    model,
    input_tokens,
    output_tokens,
):
    """
    Calculate estimated OpenAI API cost in USD.

    Returns None if the model is not found in
    settings.AI_MODEL_PRICING.
    """
    pricing = settings.AI_MODEL_PRICING.get(model)

    if not pricing:
        return None

    input_cost = (
        input_tokens / 1_000_000
    ) * pricing["input_per_million"]

    output_cost = (
        output_tokens / 1_000_000
    ) * pricing["output_per_million"]

    return input_cost + output_cost


def calculate_user_cost(
    user,
    year=None,
    month=None,
):
    """
    Calculate a user's estimated AI cost in USD.

    If year and month are supplied, only usage from
    that calendar month is included.

    Unknown models are skipped because their cost
    cannot be calculated safely.
    """
    logs = BotUsageLog.objects.filter(
        user=user,
    )

    if year is not None:
        logs = logs.filter(
            timestamp__year=year,
        )

    if month is not None:
        logs = logs.filter(
            timestamp__month=month,
        )

    total_cost = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    billable_requests = 0
    unknown_model_requests = 0

    for log in logs:
        cost = calculate_ai_cost(
            log.model,
            log.input_tokens,
            log.output_tokens,
        )

        if cost is None:
            unknown_model_requests += 1
            continue

        total_cost += cost
        total_input_tokens += log.input_tokens
        total_output_tokens += log.output_tokens
        total_tokens += log.tokens_used
        billable_requests += 1

    return {
        "cost_usd": total_cost,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "billable_requests": billable_requests,
        "unknown_model_requests": unknown_model_requests,
    }


def calculate_user_current_month_cost(user):
    """
    Calculate the user's AI usage for the current
    calendar month.
    """
    now = datetime.now(
        dt_timezone.utc
    )

    return calculate_user_cost(
        user=user,
        year=now.year,
        month=now.month,
    )