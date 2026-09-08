"""
API views for managing bots and chat interactions.

Includes endpoints for:

- Listing and creating bots
- Viewing, updating, and deleting individual bots
- Chatting with a bot via OpenAI integration
- Fetching the user's authentication token
"""

import os

import openai

from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai_assistant.accounts.plan_utils import get_ai_usage_status
from ai_assistant.bots.knowledge_utils import (
    check_message_domain,
    render_system_message,
    search_relevant_chunks,
)
from ai_assistant.bots.models import Bot, ChatMessage
from ai_assistant.bots.serializers import BotSerializer
from ai_assistant.dashboard.models import BotUsageLog


class BotListCreateAPIView(generics.ListCreateAPIView):
    """
    List all bots owned by the authenticated user
    and allow new bots to be created.
    """

    serializer_class = BotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Bot.objects.filter(
            owner=self.request.user
        )

    def perform_create(self, serializer):
        serializer.save(
            owner=self.request.user
        )


class BotDetailAPIView(
    generics.RetrieveUpdateDestroyAPIView
):
    """
    Retrieve, update, or delete a bot owned
    by the authenticated user.
    """

    serializer_class = BotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Bot.objects.filter(
            owner=self.request.user
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def api_bot_chat(request, bot_id):
    """
    Send a message to an authenticated user's bot.

    The request follows the same core AI rules used by
    the web interface:

    - Plan and usage limits
    - Strict category enforcement
    - Semantic knowledge retrieval
    - Conversation history
    - Token and model logging
    - Daily usage tracking
    """

    user = request.user
    profile = user.profile

    try:
        bot = Bot.objects.get(
            id=bot_id,
            owner=user,
        )

    except Bot.DoesNotExist:
        return Response(
            {
                "error": "Bot not found.",
            },
            status=status.HTTP_404_NOT_FOUND,
        )

    user_message = str(
        request.data.get(
            "message",
            "",
        )
    ).strip()

    if not user_message:
        return Response(
            {
                "error": "Message cannot be empty.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    usage_status = get_ai_usage_status(user)

    if not usage_status["allowed"]:
        if usage_status["daily_limit_reached"]:
            return Response(
                {
                    "error": (
                        "Daily AI message limit reached."
                    ),
                    "plan": usage_status["plan"],
                    "daily_messages_used": (
                        usage_status[
                            "daily_messages_used"
                        ]
                    ),
                    "daily_limit": (
                        usage_status[
                            "daily_message_limit"
                        ]
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        if usage_status[
            "monthly_cost_limit_reached"
        ]:
            return Response(
                {
                    "error": (
                        "Monthly AI usage limit reached."
                    ),
                    "plan": usage_status["plan"],
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {
                "error": "AI usage is unavailable.",
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        domain_result = check_message_domain(
            bot,
            user_message,
        )

    except Exception as error:
        return Response(
            {
                "error": "Category validation error.",
                "details": str(error),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    classifier_tokens = domain_result[
        "tokens_used"
    ]

    if classifier_tokens > 0:
        BotUsageLog.objects.create(
            user=user,
            bot=bot,
            tokens_used=classifier_tokens,
            input_tokens=domain_result[
                "input_tokens"
            ],
            output_tokens=domain_result[
                "output_tokens"
            ],
            model=domain_result["model"],
        )

    if not domain_result["in_domain"]:
        bot_response = (
            f"I specialize in "
            f"{bot.get_category_display()}. "
            f"Please ask me something related "
            f"to that category."
        )

        ChatMessage.objects.create(
            bot=bot,
            user=user,
            message=user_message,
            sender="user",
        )

        ChatMessage.objects.create(
            bot=bot,
            user=user,
            message=bot_response,
            sender="bot",
        )

        profile.increment_message_count()

        return Response(
            {
                "response": bot_response,
                "plan": profile.plan,
                "tokens_used": classifier_tokens,
                "input_tokens": domain_result[
                    "input_tokens"
                ],
                "output_tokens": domain_result[
                    "output_tokens"
                ],
                "model": domain_result["model"],
                "daily_messages_used": (
                    profile.daily_message_count
                ),
                "daily_limit": (
                    usage_status[
                        "daily_message_limit"
                    ]
                ),
                "in_domain": False,
            }
        )

    try:
        relevant_chunks = search_relevant_chunks(
            bot,
            user_message,
            top_k=3,
        )

    except Exception as error:
        return Response(
            {
                "error": (
                    "Knowledge retrieval failed."
                ),
                "details": str(error),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    knowledge_text = "\n\n".join(
        relevant_chunks
    )

    system_message = render_system_message(
        bot,
        knowledge_text,
    )

    previous_messages = list(
        ChatMessage.objects.filter(
            bot=bot,
            user=user,
        )
        .order_by("-timestamp")[:20]
    )

    previous_messages.reverse()

    conversation = [
        {
            "role": "system",
            "content": system_message,
        }
    ]

    for previous_message in previous_messages:
        role = (
            "user"
            if previous_message.sender == "user"
            else "assistant"
        )

        conversation.append(
            {
                "role": role,
                "content": previous_message.message,
            }
        )

    conversation.append(
        {
            "role": "user",
            "content": user_message,
        }
    )

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        return Response(
            {
                "error": (
                    "OPENAI_API_KEY is missing."
                ),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    openai.api_key = api_key

    requested_model = "gpt-4o-mini"

    try:
        response = openai.ChatCompletion.create(
            model=requested_model,
            messages=conversation,
            max_tokens=500,
        )

    except Exception as error:
        return Response(
            {
                "error": "OpenAI API error.",
                "details": str(error),
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    bot_response = (
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
        requested_model,
    )

    if tokens_used > 0:
        BotUsageLog.objects.create(
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
        message=user_message,
        sender="user",
    )

    ChatMessage.objects.create(
        bot=bot,
        user=user,
        message=bot_response,
        sender="bot",
    )

    profile.increment_message_count()

    return Response(
        {
            "response": bot_response,
            "plan": profile.plan,
            "tokens_used": (
                classifier_tokens
                + tokens_used
            ),
            "input_tokens": (
                domain_result[
                    "input_tokens"
                ]
                + input_tokens
            ),
            "output_tokens": (
                domain_result[
                    "output_tokens"
                ]
                + output_tokens
            ),
            "model": model_name,
            "daily_messages_used": (
                profile.daily_message_count
            ),
            "daily_limit": (
                usage_status[
                    "daily_message_limit"
                ]
            ),
            "in_domain": True,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def get_user_token(request):
    """
    Return the authentication token for the
    authenticated user.
    """

    from rest_framework.authtoken.models import Token

    token, _ = Token.objects.get_or_create(
        user=request.user
    )

    return Response(
        {
            "token": token.key,
        }
    )