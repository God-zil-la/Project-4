from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from ai_assistant.bots.request_validation import validate_request_object
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ai_assistant.accounts.models import UserProfile
from ai_assistant.accounts.email_utils import (
    public_origin,
    send_account_email,
)
from ai_assistant.accounts.tokens import account_activation_token
from ai_assistant.bots.chat_service import (
    ChatRateLimitError,
    ChatServiceError,
    ChatUsageLimitError,
    process_bot_message,
)
from ai_assistant.bots.models import Bot

class IOSLoginAPIView(APIView):
    """Authenticate native app users with case-insensitive usernames."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        username = str(request.data.get("username", "")).strip()
        password = request.data.get("password", "")

        if not username or not password:
            return Response(
                {"error": "Username and password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(username__iexact=username)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return Response(
                {"error": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        authenticated_user = authenticate(
            request=request,
            username=user.username,
            password=password,
        )

        if authenticated_user is None:
            return Response(
                {"error": "Invalid username or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        token, _ = Token.objects.get_or_create(
            user=authenticated_user,
        )

        return Response(
            {
                "token": token.key,
                "username": authenticated_user.username,
            },
            status=status.HTTP_200_OK,
        )

class IOSMeAPIView(APIView):
    """Return the authenticated native app user."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        profile = request.user.profile

        return Response(
            {
                "username": request.user.username,
                "email": request.user.email,
                "plan": profile.effective_plan,
            },
            status=status.HTTP_200_OK,
        )

class IOSRegisterAPIView(APIView):
    """Register native app users with email verification."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        username = User.normalize_username(
            str(request.data.get("username", "")).strip()
        )
        email = str(request.data.get("email", "")).strip()
        password = request.data.get("password", "")
        password2 = request.data.get("password2", "")

        if not all([username, email, password, password2]):
            return Response(
                {"error": "All fields are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if password != password2:
            return Response(
                {"error": "Passwords do not match."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username__iexact=username).exists():
            return Response(
                {
                    "error": (
                        "Username already exists. "
                        "Please choose another."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(email__iexact=email).exists():
            return Response(
                {
                    "error": (
                        "An account with this email address "
                        "already exists."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_email(email)
            validate_password(
                password,
                User(username=username, email=email),
            )
        except ValidationError as exc:
            return Response(
                {"errors": exc.messages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    is_active=False,
                )
        except IntegrityError:
            if not User.objects.filter(
                username__iexact=username
            ).exists():
                raise

            return Response(
                {
                    "error": (
                        "Username already exists. "
                        "Please choose another."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        origin = public_origin(request)

        uid = urlsafe_base64_encode(
            force_bytes(user.pk)
        )
        token = account_activation_token.make_token(user)

        activation_path = reverse(
            "accounts:activate",
            kwargs={
                "uidb64": uid,
                "token": token,
            },
        )

        activation_url = f"{origin}{activation_path}"

        context = {
            "user": user,
            "domain": origin.split("://", 1)[1],
            "activation_url": activation_url,
        }

        subject = "Verify your email - AI Assistant"

        text_content = render_to_string(
            "accounts/activation_email.txt",
            context,
        )

        html_content = render_to_string(
            "accounts/activation_email.html",
            context,
        )

        email_message = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [email],
        )
        email_message.attach_alternative(
            html_content,
            "text/html",
        )

        transaction.on_commit(
            lambda: send_account_email(email_message)
        )

        return Response(
            {
                "message": (
                    "Account created. "
                    "Please verify your email."
                ),
                "email": email,
            },
            status=status.HTTP_201_CREATED,
        )        


class PublicChatAPIView(APIView):
    """
    Public API endpoint for sending messages to a bot
    using an API key.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        api_key = request.headers.get("X-API-KEY")

        if not api_key:
            return Response(
                {
                    "error": "API key required.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            profile = UserProfile.objects.get(
                api_key=api_key,
                user__is_active=True,
            )
            user = profile.user

        except UserProfile.DoesNotExist:
            return Response(
                {
                    "error": "Invalid API key.",
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if profile.plan != UserProfile.PLAN_PRO:
            return Response(
                {
                    "error": "API access requires the Pro plan.",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        validate_request_object(
            request.data,
            ("message", "conversation_id"),
            ("conversation_id",),
        )

        bot_id = request.data.get("bot_id")

        message = str(
            request.data.get(
                "message",
                "",
            )
        ).strip()

        conversation_id = request.data.get("conversation_id")

        if conversation_id is not None:
            conversation_id = str(conversation_id).strip()

            if not conversation_id:
                conversation_id = None

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

        except (Bot.DoesNotExist, ValueError, TypeError):
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
                conversation=conversation_id,
            )

        except ChatUsageLimitError as error:
            usage_status = error.usage_status

            response_data = {
                "error": str(error),
                "plan": usage_status["plan"],
            }

            if usage_status["monthly_message_limit_reached"]:
                response_data.update(
                    {
                        "monthly_messages_used": (
                            usage_status["monthly_messages_used"]
                        ),
                        "monthly_limit": (
                            usage_status["monthly_message_limit"]
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
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            result,
            status=status.HTTP_200_OK,
        )