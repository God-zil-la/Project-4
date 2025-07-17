from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ai_assistant.bots.models import Bot, ChatMessage
from ai_assistant.bots.serializers import BotSerializer
from ai_assistant.bots.utils import generate_embedding, search_relevant_chunks

import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")


class BotListCreateAPIView(generics.ListCreateAPIView):
    serializer_class = BotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Bot.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)


class BotDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = BotSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Bot.objects.filter(owner=self.request.user)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def api_bot_chat(request, bot_id):
    user = request.user
    try:
        bot = Bot.objects.get(id=bot_id, owner=user)
    except Bot.DoesNotExist:
        return Response(
            {"error": "Bot not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    user_message = request.data.get('message', '').strip()
    if not user_message:
        return Response(
            {"error": "Message cannot be empty."},
            status=status.HTTP_400_BAD_REQUEST
        )

    ChatMessage.objects.create(
        bot=bot,
        user=user,
        message=user_message,
        sender='user'
    )

    try:
        user_embedding = generate_embedding(user_message)
    except Exception as e:
        return Response(
            {"error": f"Embedding generation failed: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    context_text = ""
    if user_embedding:
        relevant_chunks = search_relevant_chunks(
            bot,
            user_embedding,
            top_k=10
        )
        MAX_CONTEXT_CHARS = 2000
        context_chunks = []
        total_len = 0

        for chunk in relevant_chunks:
            text = chunk.text.strip()
            if not text:
                continue
            if total_len + len(text) > MAX_CONTEXT_CHARS:
                break
            context_chunks.append(f"- {text}")
            total_len += len(text)

        if context_chunks:
            context_text = "\n".join(context_chunks)

    category_prompt = {
        "general": "You are a helpful assistant who answers clearly "
                   "and concisely.",
        "fitness": "You are a fitness coach giving motivating, accurate "
                   "health advice.",
        "finance": "You are a financial expert explaining money, budgeting, "
                   "and investment tips.",
        "funny": "You are a stand-up comedian who always responds with "
                 "jokes and humor.",
        "support": "You are a kind, supportive friend who is empathetic "
                   "and comforting.",
        "tech": "You are a tech specialist explaining technology simply "
                "and clearly.",
    }.get(bot.category, "You are a helpful assistant.")

    if context_text:
        system_message = (
            f"{category_prompt}\n\n"
            "You also have access to the following knowledge base entries "
            "that may help answer the question. Use them if relevant:\n"
            f"{context_text}"
        )
    else:
        system_message = category_prompt

    previous_messages = ChatMessage.objects.filter(
        bot=bot,
        user=user
    ).order_by('timestamp')

    conversation = [{"role": "system", "content": system_message}]
    for msg in previous_messages:
        role = "user" if msg.sender == "user" else "assistant"
        conversation.append({
            "role": role,
            "content": msg.message
        })

    conversation.append({
        "role": "user",
        "content": user_message
    })

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=conversation
        )
        bot_response = response.choices[0].message.content.strip()
    except Exception as e:
        return Response(
            {
                "error": f"OpenAI error: {str(e)}"
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    ChatMessage.objects.create(
        bot=bot,
        user=user,
        message=bot_response,
        sender='bot'
    )

    return Response({"response": bot_response})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def get_user_token(request):
    from rest_framework.authtoken.models import Token
    token, _ = Token.objects.get_or_create(user=request.user)
    return Response({'token': token.key})
