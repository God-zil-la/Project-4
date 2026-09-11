import os

import re
import logging
import openai
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from ai_assistant.accounts.models import UserProfile
from ai_assistant.accounts.plan_utils import get_ai_usage_status
from ai_assistant.dashboard.models import BotUsageLog

from .knowledge_utils import (
    check_message_domain,
    render_system_message,
    search_relevant_chunks,
)
from .models import ChatMessage, Conversation


logger = logging.getLogger(__name__)


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
    """
    Raised when the user sends too many AI requests
    in a short period.
    """

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


def _resolve_conversation(
    user,
    bot,
    conversation=None,
):
    """
    Resolve the conversation used for the current message.

    Existing callers that do not yet provide a conversation
    continue using the user's most recent conversation for
    that bot.

    New API and mobile clients can provide either a
    Conversation instance or its public UUID.
    """

    if conversation is None:
        existing_conversation = (
            Conversation.objects.filter(
                user=user,
                bot=bot,
            )
            .order_by("-updated_at", "-created_at")
            .first()
        )

        if existing_conversation is not None:
            return existing_conversation

        return Conversation.objects.create(
            user=user,
            bot=bot,
        )

    if isinstance(conversation, Conversation):
        resolved_conversation = conversation

    else:
        try:
            resolved_conversation = (
                Conversation.objects.get(
                    public_id=conversation,
                )
            )

        except (
            Conversation.DoesNotExist,
            ValidationError,
            ValueError,
            TypeError,
        ) as error:
            raise ChatServiceError(
                "Conversation not found."
            ) from error

    if resolved_conversation.user_id != user.id:
        raise ChatServiceError(
            "Conversation does not belong to this user."
        )

    if resolved_conversation.bot_id != bot.id:
        raise ChatServiceError(
            "Conversation does not belong to this bot."
        )

    return resolved_conversation


def _set_conversation_title(
    conversation,
    message,
):
    """
    Create a short title from the first user message.
    """

    if conversation.title:
        return

    clean_title = " ".join(
        str(message).split()
    ).strip()

    if not clean_title:
        return

    conversation.title = clean_title[:80]
    conversation.save(
        update_fields=[
            "title",
            "updated_at",
        ]
    )


def _touch_conversation(conversation):
    """
    Update the conversation activity timestamp.
    """

    Conversation.objects.filter(
        pk=conversation.pk,
    ).update(
        updated_at=timezone.now(),
    )


def _build_history(
    conversation,
    system_message,
):
    """
    Build OpenAI conversation history from messages
    belonging only to the selected conversation.
    """

    previous_messages = list(
        ChatMessage.objects.filter(
            conversation=conversation,
        )
        .order_by("-timestamp")[
            :CHAT_HISTORY_LIMIT
        ]
    )

    previous_messages.reverse()

    messages = [
        {
            "role": "system",
            "content": system_message,
        }
    ]

    for previous_message in previous_messages:
        messages.append(
            {
                "role": (
                    "user"
                    if previous_message.sender
                    == ChatMessage.SENDER_USER
                    else "assistant"
                ),
                "content": previous_message.message,
            }
        )

    return messages


@transaction.atomic
def _save_chat_exchange(
    conversation,
    bot,
    user,
    user_message,
    assistant_message,
):
    """
    Save one complete user and assistant exchange.
    """

    ChatMessage.objects.create(
        conversation=conversation,
        bot=bot,
        user=user,
        sender=ChatMessage.SENDER_USER,
        message=user_message,
    )

    ChatMessage.objects.create(
        conversation=conversation,
        bot=bot,
        user=user,
        sender=ChatMessage.SENDER_ASSISTANT,
        message=assistant_message,
    )

    _touch_conversation(conversation)
    user.profile.increment_message_count()


def _check_rate_limit(user, profile):
    rate_limit = settings.AI_RATE_LIMITS.get(
        getattr(profile, "effective_plan", profile.plan),
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

    try:
        # Retry expiry races without overwriting a new counter.
        for attempt in range(3):
            if cache.add(cache_key, 1, timeout=60):
                return
            try:
                request_count = cache.incr(cache_key)
                break
            except ValueError:
                continue
        else:
            raise ChatServiceError("AI service is temporarily unavailable.")
    except ChatServiceError:
        raise
    except Exception:
        logger.error("Rate-limit cache unavailable.")
        raise ChatServiceError("AI service is temporarily unavailable.") from None

    if request_count > rate_limit:
        raise ChatRateLimitError(
            (
                "Too many AI requests. "
                "Please try again shortly."
            ),
            retry_after_seconds=60,
        )


def process_bot_message(
    user,
    bot,
    message,
    conversation=None,
):
    """
    Process one bot message using the shared AI pipeline.

    The pipeline handles:

    - Account usage limits
    - Short-term rate limiting
    - Conversation resolution
    - Category enforcement
    - Knowledge retrieval
    - Conversation-specific history
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

    active_conversation = (
        _resolve_conversation(
            user=user,
            bot=bot,
            conversation=conversation,
        )
    )

    _set_conversation_title(
        active_conversation,
        message,
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

        _save_chat_exchange(
            conversation=active_conversation,
            bot=bot,
            user=user,
            user_message=message,
            assistant_message=response_text,
        )


        return {
            "response": response_text,
            "conversation_id": str(
                active_conversation.public_id
            ),
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

    try:
        knowledge_result = search_relevant_chunks(
            bot,
            message,
            top_k=3,
            include_usage=True,
        )

    except Exception:
        logger.error(
            "Knowledge retrieval failed for bot %s.",
            bot.pk,
        )

        knowledge_result = {
            "chunks": [],
            "tokens_used": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "model": None,
        }

    embedding_tokens = knowledge_result[
        "tokens_used"
    ]

    embedding_input_tokens = knowledge_result[
        "input_tokens"
    ]

    embedding_output_tokens = knowledge_result[
        "output_tokens"
    ]

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

    openai_messages = _build_history(
        active_conversation,
        system_message,
    )

    openai_messages.append(
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
            "AI service is temporarily unavailable."
        )

    openai.api_key = api_key

    response = openai.ChatCompletion.create(
        model=CHAT_MODEL,
        messages=openai_messages,
        max_tokens=CHAT_MAX_TOKENS,
    )

    response_text = (
        response
        .choices[0]
        .message["content"]
        .strip()
    )

    # Clean up duplicated Markdown links produced by the model.
    response_text = re.sub(
        r"\[\[(https?://[^\]\s]+)\]\(\1\)\]\(\1\)",
        r"\1",
        response_text,
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

    _save_chat_exchange(
        conversation=active_conversation,
        bot=bot,
        user=user,
        user_message=message,
        assistant_message=response_text,
    )


    return {
        "response": response_text,
        "conversation_id": str(
            active_conversation.public_id
        ),
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
