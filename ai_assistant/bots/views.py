import json
import time
import logging

from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponseNotAllowed
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect

from openai import OpenAI

from ai_assistant.accounts.models import UserProfile
from .models import Bot, ChatMessage
from ai_assistant.dashboard.models import BotUsageLog
from .utils import generate_embedding, search_relevant_chunks

logger = logging.getLogger(__name__)
client = OpenAI()

@login_required
@csrf_protect
def ajax_chat(request, bot_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    data = json.loads(request.body)
    user_message = data.get('message', '').strip()
    if not user_message:
        return JsonResponse({'response': "⚠️ Please enter a message."}, status=400)

    # Only allow access to bots owned by the logged-in user
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)

    # Get or create user profile and reset daily count if needed
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.reset_daily_count()

    # Enforce daily message limit for non-subscribed users
    if not profile.is_subscribed and profile.daily_message_count >= 10:
        return JsonResponse({'response': "⚠️ Daily limit reached. Please subscribe to continue chatting."}, status=429)

    # Save user message
    ChatMessage.objects.create(bot=bot, user=request.user, message=user_message, sender='user')

    # Generate user message embedding for knowledge retrieval
    user_embedding = None
    try:
        user_embedding = generate_embedding(user_message)
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")

    # Build context from relevant knowledge chunks
    context_text = ""
    if user_embedding:
        relevant_chunks = search_relevant_chunks(bot, user_embedding, top_k=10)
        MAX_CONTEXT_CHARS = 1500

        context_chunks = []
        total_len = 0
        for chunk in relevant_chunks:
            chunk_len = len(chunk.text)
            if total_len + chunk_len > MAX_CONTEXT_CHARS:
                break
            context_chunks.append(chunk.text)
            total_len += chunk_len

        context_text = "\n\n".join(context_chunks)

    # Prepare system prompt based on bot category
    category_prompt = {
        "general": "You are a helpful assistant who answers clearly and concisely.",
        "fitness": "You are a fitness coach giving motivating, accurate health advice.",
        "finance": "You are a financial expert explaining money, budgeting, and investment tips.",
        "funny": "You are a stand-up comedian who always responds with jokes and humor.",
        "support": "You are a kind, supportive friend who is empathetic and comforting.",
        "tech": "You are a tech specialist explaining technology simply and clearly.",
    }.get(bot.category, "You are a helpful assistant.")

    system_message = category_prompt
    if context_text:
        system_message += f"\n\nHere is some relevant knowledge:\n{context_text}"

    # Call OpenAI API with retry on rate limits
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
            )
            bot_response = response.choices[0].message.content.strip()
            usage = response.usage
            break
        except Exception as e:
            err_msg = str(e).lower()
            if "rate limit" in err_msg or "too many requests" in err_msg:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return JsonResponse({'response': "⚠️ Rate limit exceeded. Please try again later."}, status=429)
            else:
                logger.error(f"OpenAI API error: {e}")
                bot_response = f"[API Error] {str(e)}"
                usage = None
                break

    # Save bot response
    ChatMessage.objects.create(bot=bot, user=request.user, message=bot_response, sender='bot')

    # Increment daily message count
    profile.increment_message_count()

    # Log usage for analytics
    if usage:
        BotUsageLog.objects.create(
            user=request.user,
            bot=bot,
            message=user_message,
            token_count=usage.total_tokens
        )

    return JsonResponse({'response': bot_response})
