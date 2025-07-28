from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from ai_assistant.accounts.models import UserProfile
from ai_assistant.bots.models import Bot, BotUsageLog
from ai_assistant.bots.openai_client import call_openai
from django.core.exceptions import ObjectDoesNotExist


class PublicChatAPIView(APIView):
    """Public API endpoint for sending messages to a bot using an API key."""

    def post(self, request, *args, **kwargs):
        """Handle POST request to process a message and return AI response."""
        api_key = request.headers.get('X-API-KEY')
        if not api_key:
            return Response({'error': 'API key required'}, status=401)

        try:
            profile = UserProfile.objects.get(api_key=api_key)
            user = profile.user
        except UserProfile.DoesNotExist:
            return Response({'error': 'Invalid API key'}, status=401)

        if not profile.is_subscribed and profile.daily_message_count >= 5:
            return Response({'error': 'Daily free limit exceeded'}, status=403)

        bot_id = request.data.get('bot_id')
        message = request.data.get('message')

        if not bot_id or not message:
            return Response({'error': 'bot_id and message are required'}, status=400)

        try:
            bot = Bot.objects.get(id=bot_id, owner=user)
        except ObjectDoesNotExist:
            return Response({'error': 'Bot not found or unauthorized'}, status=404)

        try:
            response_text = call_openai(bot, message)
        except Exception as e:
            return Response({'error': 'OpenAI API error', 'details': str(e)}, status=500)

        BotUsageLog.objects.create(
            user=user,
            bot=bot,
            tokens_used=len(message) + len(response_text)
        )
        profile.increment_message_count()

        return Response({'response': response_text})
