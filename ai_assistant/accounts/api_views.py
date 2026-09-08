from django.core.exceptions import ObjectDoesNotExist

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from ai_assistant.accounts.models import UserProfile
from ai_assistant.accounts.plan_utils import get_ai_usage_status
from ai_assistant.bots.models import Bot
from ai_assistant.bots.openai_client import call_openai
from ai_assistant.bots.knowledge_utils import check_message_domain
from ai_assistant.dashboard.models import BotUsageLog


class PublicChatAPIView(APIView):
    """
    Public API endpoint for sending messages to a bot
    using an API key.
    """

    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        api_key = request.headers.get("X-API-KEY")

        if not api_key:
            return Response(
                {
                    "error": "API key required",
                },
                status=401,
            )

        try:
            profile = UserProfile.objects.get(
                api_key=api_key
            )
            user = profile.user

        except UserProfile.DoesNotExist:
            return Response(
                {
                    "error": "Invalid API key",
                },
                status=401,
            )

        bot_id = request.data.get("bot_id")
        message = request.data.get("message")

        if not bot_id or not message:
            return Response(
                {
                    "error": (
                        "bot_id and message are required"
                    ),
                },
                status=400,
            )

        message = str(message).strip()

        if not message:
            return Response(
                {
                    "error": "Message cannot be empty",
                },
                status=400,
            )

        try:
            bot = Bot.objects.get(
                id=bot_id,
                owner=user,
            )

        except ObjectDoesNotExist:
            return Response(
                {
                    "error": (
                        "Bot not found or unauthorized"
                    ),
                },
                status=404,
            )

        # Check plan limits before processing
        # another AI request.
        usage_status = get_ai_usage_status(user)

        if not usage_status["allowed"]:
            if usage_status["daily_limit_reached"]:
                return Response(
                    {
                        "error": (
                            "Daily AI message limit "
                            "reached"
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
                    status=403,
                )

            if usage_status[
                "monthly_cost_limit_reached"
            ]:
                return Response(
                    {
                        "error": (
                            "Monthly AI usage limit "
                            "reached"
                        ),
                        "plan": usage_status["plan"],
                    },
                    status=403,
                )

            return Response(
                {
                    "error": "AI usage is unavailable",
                },
                status=403,
            )

        # Run the strict category classifier before
        # sending the message to the main AI response.
        try:
            domain_result = check_message_domain(
                bot,
                message,
            )

        except Exception as exc:
            return Response(
                {
                    "error": (
                        "Category validation error"
                    ),
                    "details": str(exc),
                },
                status=500,
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

        # Stop here if the message is outside
        # the bot's configured category.
        if not domain_result["in_domain"]:
            response_text = (
                f"I specialize in "
                f"{bot.get_category_display()}. "
                f"Please ask me something related "
                f"to that category."
            )

            profile.increment_message_count()

            return Response(
                {
                    "response": response_text,
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
                "plan": profile.plan,
                "tokens_used": (
                    classifier_tokens + tokens_used
                ),
                "input_tokens": (
                    domain_result["input_tokens"]
                    + input_tokens
                ),
                "output_tokens": (
                    domain_result["output_tokens"]
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