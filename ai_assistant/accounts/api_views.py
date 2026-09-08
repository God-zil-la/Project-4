from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from ai_assistant.accounts.models import UserProfile
from ai_assistant.bots.models import Bot
from ai_assistant.bots.openai_client import call_openai
from ai_assistant.dashboard.models import BotUsageLog


class PublicChatAPIView(APIView):
    """
    Public API endpoint for sending messages to a bot using an API key.
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        api_key = request.headers.get("X-API-KEY")

        if not api_key:
            return Response(
                {"error": "API key required"},
                status=401,
            )

        try:
            profile = UserProfile.objects.get(api_key=api_key)
            user = profile.user
        except UserProfile.DoesNotExist:
            return Response(
                {"error": "Invalid API key"},
                status=401,
            )

        # Reset the daily counter if a new day has started.
        profile.reset_daily_count()

        daily_limit = settings.FREE_PLAN_DAILY_LIMIT

        if (
            not profile.is_subscribed
            and profile.daily_message_count >= daily_limit
        ):
            return Response(
                {
                    "error": "Daily free limit exceeded",
                    "daily_limit": daily_limit,
                },
                status=403,
            )

        bot_id = request.data.get("bot_id")
        message = request.data.get("message")

        if not bot_id or not message:
            return Response(
                {"error": "bot_id and message are required"},
                status=400,
            )

        message = str(message).strip()

        if not message:
            return Response(
                {"error": "Message cannot be empty"},
                status=400,
            )

        try:
            bot = Bot.objects.get(
                id=bot_id,
                owner=user,
            )
        except ObjectDoesNotExist:
            return Response(
                {"error": "Bot not found or unauthorized"},
                status=404,
            )

        try:
            (
                response_text,
                tokens_used,
                input_tokens,
                output_tokens,
                model_name,
            ) = call_openai(
                bot,
                message,
            )

        except Exception as exc:
            return Response(
                {
                    "error": "OpenAI API error",
                    "details": str(exc),
                },
                status=500,
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

        profile.increment_message_count()

        return Response(
            {
                "response": response_text,
                "tokens_used": tokens_used,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": model_name,
                "daily_messages_used": profile.daily_message_count,
                "daily_limit": (
                    None
                    if profile.is_subscribed
                    else daily_limit
                ),
            }
        )