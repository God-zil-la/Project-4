"""
API views for managing bots and chat interactions.

Includes endpoints for:

- Listing and creating bots
- Viewing, updating, and deleting individual bots
- Chatting with a bot through the shared AI chat service
- Fetching the user's authentication token
"""

from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai_assistant.bots.chat_service import (
    ChatRateLimitError,
    ChatServiceError,
    ChatUsageLimitError,
    process_bot_message,
)
from ai_assistant.bots.models import Bot
from ai_assistant.bots.serializers import BotSerializer


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
    Send a message to an authenticated user's bot
    using the shared AI chat service.

    A conversation_id can optionally be provided to
    continue an existing conversation.

    If no conversation_id is provided, the shared
    chat service resolves or creates a conversation.
    """

    user = request.user

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

    conversation_id = request.data.get(
        "conversation_id"
    )

    if conversation_id is not None:
        conversation_id = str(
            conversation_id
        ).strip()

        if not conversation_id:
            conversation_id = None

    try:
        result = process_bot_message(
            user=user,
            bot=bot,
            message=user_message,
            conversation=conversation_id,
        )

    except ChatUsageLimitError as error:
        usage_status = error.usage_status

        response_data = {
            "error": str(error),
            "plan": usage_status["plan"],
        }

        if usage_status[
            "daily_limit_reached"
        ]:
            response_data.update(
                {
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
                }
            )

        return Response(
            response_data,
            status=status.HTTP_403_FORBIDDEN,
        )

    except ChatRateLimitError as error:
        return Response(
            {
                "error": str(error),
                "retry_after_seconds": (
                    error.retry_after_seconds
                ),
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    except ChatServiceError as error:
        return Response(
            {
                "error": str(error),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    except Exception:
        return Response(
            {
                "error": "AI processing failed.",
            },
            status=(
                status.HTTP_500_INTERNAL_SERVER_ERROR
            ),
        )

    return Response(
        result,
        status=status.HTTP_200_OK,
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