from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_assistant.accounts.models import UserProfile
from ai_assistant.bots.chat_service import (
    ChatServiceError,
    ChatUsageLimitError,
    process_bot_message,
)
from ai_assistant.bots.models import Bot


class PublicChatAPIView(APIView):
    """
    Public API endpoint for sending messages to a bot
    using an API key.
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        api_key = request.headers.get(
            "X-API-KEY"
        )

        if not api_key:
            return Response(
                {
                    "error": "API key required.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            profile = UserProfile.objects.get(
                api_key=api_key
            )
            user = profile.user

        except UserProfile.DoesNotExist:
            return Response(
                {
                    "error": "Invalid API key.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        bot_id = request.data.get(
            "bot_id"
        )

        message = str(
            request.data.get(
                "message",
                "",
            )
        ).strip()

        if not bot_id:
            return Response(
                {
                    "error": "bot_id is required.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not message:
            return Response(
                {
                    "error": "Message cannot be empty.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            bot = Bot.objects.get(
                id=bot_id,
                owner=user,
            )

        except Bot.DoesNotExist:
            return Response(
                {
                    "error": (
                        "Bot not found or unauthorized."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            result = process_bot_message(
                user=user,
                bot=bot,
                message=message,
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

        except ChatServiceError as error:
            return Response(
                {
                    "error": str(error),
                },
                status=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
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

        return Response(result)