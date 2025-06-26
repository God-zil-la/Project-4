import os
import json
import time
import logging
from datetime import timedelta

from django.template.loader import get_template
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseNotAllowed
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate

from ai_assistant.accounts.models import UserProfile
from ai_assistant.dashboard.models import BotUsageLog
from .models import Bot, ChatMessage, KnowledgeBase
from .forms import BotForm, KnowledgeBaseForm
from .utils import generate_embedding, search_relevant_chunks, extract_text, chunk_text

logger = logging.getLogger(__name__)

@login_required
def upload_knowledge(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)

    if request.method == 'POST':
        form = KnowledgeBaseForm(request.POST, request.FILES)
        if form.is_valid():
            knowledge = form.save(commit=False)
            knowledge.bot = bot
            knowledge.uploaded_by = request.user
            knowledge.save()

            from .models import KnowledgeChunk
            KnowledgeChunk.objects.filter(knowledge_file=knowledge).delete()

            try:
                text = extract_text(knowledge.file.path, knowledge.file.name)
                chunks = chunk_text(text)
                
                created_chunks = []
                for chunk_text_part in chunks:
                    chunk = KnowledgeChunk.objects.create(knowledge_file=knowledge, text=chunk_text_part)
                    created_chunks.append(chunk)

                logger.info(f"Uploaded file processed into {len(chunks)} chunks.")

                # Generate embeddings for each chunk
                for chunk in created_chunks:
                    try:
                        embedding = generate_embedding(chunk.text)
                        chunk.embedding = embedding
                        chunk.save(update_fields=['embedding'])
                    except Exception as e:
                        logger.error(f"Failed to generate embedding for chunk {chunk.id}: {e}")

                logger.info("Embeddings generated and saved for all chunks.")

            except Exception as e:
                logger.error(f"Failed to extract or chunk file: {e}")

            return redirect('bots:playground', bot_id=bot.id)
    else:
        form = KnowledgeBaseForm()

    knowledge_files = bot.knowledge_files.all()
    return render(request, 'bots/upload_knowledge.html', {
        'form': form,
        'bot': bot,
        'knowledge_files': knowledge_files
    })


@login_required
def bot_list(request):
    logger.info("bot_list view called")
    template = get_template('bots/bot_list.html')
    logger.info(f"Loaded bot_list.html from: {template.origin}")
    bots = Bot.objects.filter(owner=request.user) 
    return render(request, 'bots/bot_list.html', {'bots': bots})


@login_required
def my_bots(request):
    user_bots = Bot.objects.filter(owner=request.user)
    return render(request, 'bots/my_bots.html', {'bots': user_bots})


@login_required
def create_bot(request):
    if request.method == 'POST':
        form = BotForm(request.POST)
        if form.is_valid():
            bot = form.save(commit=False)
            bot.owner = request.user
            bot.save()
            return redirect('bots:my-bots')
    else:
        form = BotForm()
    return render(request, 'bots/create_bot.html', {'form': form})


@login_required
def bot_chat_api(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
    if request.method == 'GET':
        messages = ChatMessage.objects.filter(bot=bot, user=request.user).order_by('timestamp')
        return JsonResponse({'messages': [{'sender': m.sender, 'message': m.message} for m in messages]})
    return HttpResponseNotAllowed(['GET'])


@login_required
def edit_bot(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
    if request.method == 'POST':
        form = BotForm(request.POST, instance=bot)
        if form.is_valid():
            form.save()
            return redirect('bots:list')
    else:
        form = BotForm(instance=bot)
    return render(request, 'bots/edit_bot.html', {'form': form})


@login_required
def delete_bot(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
    if request.method == 'POST':
        bot.delete()
        return redirect('bots:list')
    return render(request, 'bots/confirm_delete.html', {'bot': bot})


@login_required
def bot_chat_playground(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
    messages = ChatMessage.objects.filter(bot=bot, user=request.user).order_by('timestamp')
    return render(request, 'bots/playground.html', {'bot': bot, 'messages': messages})


@login_required
@csrf_protect
def ajax_chat(request, bot_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    data = json.loads(request.body)
    user_message = data.get('message', '').strip()
    if not user_message:
        return JsonResponse({'response': "⚠️ Please enter a message."}, status=400)

    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)  # Fixed owner filter here

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.reset_daily_count()

    if not profile.is_subscribed and profile.daily_message_count >= 10:
        return JsonResponse(
            {'response': "⚠️ Daily limit reached. Please subscribe to continue chatting."},
            status=429
        )

    ChatMessage.objects.create(bot=bot, user=request.user, message=user_message, sender='user')

    user_embedding = None
    try:
        user_embedding = generate_embedding(user_message)
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}")

    context_text = ""
    if user_embedding:
        relevant_chunks = search_relevant_chunks(bot, user_embedding, top_k=10)  # can increase top_k
        MAX_CONTEXT_CHARS = 1500  # max chars to inject

        context_chunks = []
        total_len = 0
        for chunk in relevant_chunks:
            chunk_len = len(chunk.text)
            if total_len + chunk_len > MAX_CONTEXT_CHARS:
                break
            context_chunks.append(chunk.text)
            total_len += chunk_len

        context_text = "\n\n".join(context_chunks)

    category_prompt = {
        "general": "You are a helpful assistant who answers clearly and concisely.",
        "fitness": "You are a fitness coach giving motivating, accurate health advice.",
        "finance": "You are a financial expert explaining money, budgeting, and investment tips.",
        "funny": "You are a stand-up comedian who always responds with jokes and humor.",
        "support": "You are a kind, supportive friend who is empathetic and comforting.",
        "tech": "You are a tech specialist explaining technology simply and clearly.",
    }.get(bot.category, "You are a helpful assistant.")

    system_message = f"{category_prompt}"
    if context_text:
        system_message += f"\n\nHere is some relevant knowledge:\n{context_text}"

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

    ChatMessage.objects.create(bot=bot, user=request.user, message=bot_response, sender='bot')
    profile.increment_message_count()

    if usage:
        BotUsageLog.objects.create(
            user=request.user,
            bot=bot,
            message=user_message,
            token_count=usage.total_tokens
        )

    return JsonResponse({'response': bot_response})


@staff_member_required
def admin_dashboard(request):
    from django.contrib.auth.models import User
    users = User.objects.all()
    bots = Bot.objects.all()
    messages = ChatMessage.objects.order_by('-timestamp')[:50]

    total_logs = BotUsageLog.objects.count()

    top_bots = (
        BotUsageLog.objects.values('bot__name')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    top_users = (
        BotUsageLog.objects.values('user__username')
        .annotate(count=Count('id'))
        .order_by('-count')[:5]
    )

    today = timezone.now().date()
    week_ago = today - timedelta(days=6)

    daily_logs = (
        BotUsageLog.objects
        .filter(timestamp__date__gte=week_ago)
        .annotate(day=TruncDate('timestamp'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    chart_labels = [entry['day'].strftime('%b %d') for entry in daily_logs]
    chart_data = [entry['count'] for entry in daily_logs]

    return render(request, 'bots/admin_dashboard.html', {
        'users': users,
        'bots': bots,
        'messages': messages,
        'total_logs': total_logs,
        'top_bots': top_bots,
        'top_users': top_users,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
    })


@staff_member_required
def analytics_dashboard(request):
    usage_by_bot = (
        BotUsageLog.objects.values("bot__name")
        .annotate(total=Count("id"))
        .order_by("-total")
    )
    usage_by_user = (
        BotUsageLog.objects.values("user__username")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    bot_data = {
        "labels": [entry["bot__name"] for entry in usage_by_bot],
        "counts": [entry["total"] for entry in usage_by_bot],
    }

    user_data = {
        "labels": [entry["user__username"] for entry in usage_by_user],
        "counts": [entry["total"] for entry in usage_by_user],
    }

    return render(request, "bots/analytics_dashboard.html", {
        "bot_data": json.dumps(bot_data),
        "user_data": json.dumps(user_data),
    })
