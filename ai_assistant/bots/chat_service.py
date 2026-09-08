import os

import openai
from django.conf import settings
from django.core.cache import cache

from ai_assistant.accounts.models import UserProfile
from ai_assistant.accounts.plan_utils import get_ai_usage_status
from ai_assistant.dashboard.models import BotUsageLog

from .knowledge_utils import (
    check_message_domain,
    render_system_message,
    search_relevant_chunks,
)
from .models import ChatMessage


CHAT_MODEL = "gpt-4o-mini"
CHAT_MAX_TOKENS = 500
CHAT_HISTORY_LIMIT = 20


class ChatServiceError(Exception):
    """Base exception for chat service errors."""


class ChatUsageLimitError(ChatServiceError):
    """Raised when the user's AI usage limit is reached."""

    def __init__(self, message, usage_status):
        super().__init__(message)
        self.usage_status = usage_status


class ChatRateLimitError(ChatServiceError):
    """Raised when the user sends too many AI requests in a short period."""

    def __init__(self, message, retry_after_seconds):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


def _log_usage(
    user,
    bot,
    tokens_used,
    input_tokens,
    output_tokens,
    model,
):
    if tokens_used <= 0:
        return

    BotUsageLog.objects.create(
        user=user,
        bot=bot,
        tokens_used=tokens_used,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model,
    )


def _build_history(
    bot,
    user,
    system_message,
):
    previous_messages = list(
        ChatMessage.objects.filter(
            bot=bot,
            user=user,
        )
        .order_by("-timestamp")[
            :CHAT_HISTORY_LIMIT
        ]
    )

    previous_messages.reverse()

    conversation = [
        {
            "role": "system",
            "content": system_message,
        }
    ]

    for previous_message in previous_messages:
        conversation.append(
            {
                "role": (
                    "user"
                    if previous_message.sender == "user"
                    else "assistant"
                ),
                "content": previous_message.message,
            }
        )

    return conversation


def _check_rate_limit(user, profile):
    rate_limit = settings.AI_RATE_LIMITS.get(
        profile.plan,
        settings.AI_RATE_LIMITS[
            UserProfile.PLAN_FREE
        ],
    )

    if rate_limit is None:
        return

    cache_key = (
        f"ai-rate-limit:"
        f"{user.pk}"
    )

    added = cache.add(
        cache_key,
        1,
        timeout=60,
    )

    if added:
        return

    try:
        request_count = cache.incr(
            cache_key
        )
    except ValueError:
        cache.set(
            cache_key,
            1,
            timeout=60,
        )
        return

    if request_count > rate_limit:
        raise ChatRateLimitError(
            "Too many AI requests. Please try again shortly.",
            retry_after_seconds=60,
        )


def process_bot_message(
    user,
    bot,
    message,
):
    """
    Process one bot message using the shared AI pipeline.

    The pipeline handles:

    - Account usage limits
    - Short-term rate limiting
    - Category enforcement
    - Knowledge retrieval
    - Conversation history
    - OpenAI response generation
    - Token usage logging
    - Chat message persistence
    - Daily message tracking
    """

    message = str(message).strip()

    if not message:
        raise ValueError(
            "Message cannot be empty."
        )

    profile = getattr(
        user,
        "profile",
        None,
    )

    if profile is None:
        raise ChatServiceError(
            "User profile not found."
        )

    _check_rate_limit(
        user,
        profile,
    )

    usage_status = get_ai_usage_status(
        user
    )

    if not usage_status["allowed"]:
        if usage_status[
            "daily_limit_reached"
        ]:
            raise ChatUsageLimitError(
                "Daily AI message limit reached.",
                usage_status,
            )

        if usage_status[
            "monthly_cost_limit_reached"
        ]:
            raise ChatUsageLimitError(
                "Monthly AI usage limit reached.",
                usage_status,
            )

        raise ChatUsageLimitError(
            "AI usage is unavailable.",
            usage_status,
        )

    domain_result = check_message_domain(
        bot,
        message,
    )

    classifier_tokens = domain_result[
        "tokens_used"
    ]

    classifier_input_tokens = domain_result[
        "input_tokens"
    ]

    classifier_output_tokens = domain_result[
        "output_tokens"
    ]

    _log_usage(
        user=user,
        bot=bot,
        tokens_used=classifier_tokens,
        input_tokens=classifier_input_tokens,
        output_tokens=classifier_output_tokens,
        model=domain_result["model"],
    )

    if not domain_result["in_domain"]:
        response_text = (
            f"I specialize in "
            f"{bot.get_category_display()}. "
            f"Please ask me something related "
            f"to that category."
        )

        ChatMessage.objects.create(
            bot=bot,
            user=user,
            sender="user",
            message=message,
        )

        ChatMessage.objects.create(
            bot=bot,
            user=user,
            sender="assistant",
            message=response_text,
        )

        profile.increment_message_count()

        return {
            "response": response_text,
            "plan": profile.plan,
            "tokens_used": classifier_tokens,
            "input_tokens": (
                classifier_input_tokens
            ),
            "output_tokens": (
                classifier_output_tokens
            ),
            "model": domain_result["model"],
            "daily_messages_used": (
                profile.daily_message_count
            ),
            "daily_limit": usage_status[
                "daily_message_limit"
            ],
            "in_domain": False,
        }

    knowledge_result = search_relevant_chunks(
        bot,
        message,
        top_k=3,
        include_usage=True,
    )

    embedding_tokens = knowledge_result[
        "tokens_used"
    ]

    embedding_input_tokens = (
        knowledge_result["input_tokens"]
    )

    embedding_output_tokens = (
        knowledge_result["output_tokens"]
    )

    _log_usage(
        user=user,
        bot=bot,
        tokens_used=embedding_tokens,
        input_tokens=embedding_input_tokens,
        output_tokens=embedding_output_tokens,
        model=knowledge_result["model"],
    )

    knowledge_text = "\n\n".join(
        knowledge_result["chunks"]
    )

    system_message = render_system_message(
        bot,
        knowledge_text,
    )

    conversation = _build_history(
        bot,
        user,
        system_message,
    )

    conversation.append(
        {
            "role": "user",
            "content": message,
        }
    )

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        raise ChatServiceError(
            "OPENAI_API_KEY is missing."
        )

    openai.api_key = api_key

    response = openai.ChatCompletion.create(
        model=CHAT_MODEL,
        messages=conversation,
        max_tokens=CHAT_MAX_TOKENS,
    )

    response_text = (
        response
        .choices[0]
        .message["content"]
        .strip()
    )

    response_usage = response.get(
        "usage",
        {},
    )

    input_tokens = response_usage.get(
        "prompt_tokens",
        0,
    )

    output_tokens = response_usage.get(
        "completion_tokens",
        0,
    )

    tokens_used = response_usage.get(
        "total_tokens",
        0,
    )

    model_name = response.get(
        "model",
        CHAT_MODEL,
    )

    _log_usage(
        user=user,
        bot=bot,
        tokens_used=tokens_used,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        model=model_name,
    )

    ChatMessage.objects.create(
        bot=bot,
        user=user,
        sender="user",
        message=message,
    )

    ChatMessage.objects.create(
        bot=bot,
        user=user,
        sender="assistant",
        message=response_text,
    )

    profile.increment_message_count()

    return {
        "response": response_text,
        "plan": profile.plan,
        "tokens_used": (
            classifier_tokens
            + embedding_tokens
            + tokens_used
        ),
        "input_tokens": (
            classifier_input_tokens
            + embedding_input_tokens
            + input_tokens
        ),
        "output_tokens": (
            classifier_output_tokens
            + embedding_output_tokens
            + output_tokens
        ),
        "model": model_name,
        "daily_messages_used": (
            profile.daily_message_count
        ),
        "daily_limit": usage_status[
            "daily_message_limit"
        ],
        "in_domain": True,
    }