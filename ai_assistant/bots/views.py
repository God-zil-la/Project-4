# Standard library imports
import os
import json
import time
import logging
import traceback
from datetime import timedelta

# Django imports
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.utils import timezone
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseNotAllowed

# Third-party imports
import openai
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token

# Local app imports
from ai_assistant.accounts.models import UserProfile
from ai_assistant.dashboard.models import BotUsageLog
from .models import Bot, ChatMessage, KnowledgeBase, KnowledgeChunk
from .forms import BotForm, KnowledgeBaseForm
from .utils import generate_embedding, search_relevant_chunks
from .utils import extract_text, chunk_text

openai.api_key = os.getenv("OPENAI_API_KEY")
logger = logging.getLogger(__name__)


@login_required
def bot_list(request):
    """Display a list of bots owned by the current user."""
    logger.info("bot_list view called")
    bots = Bot.objects.filter(owner=request.user)
    return render(request, 'bots/bot_list.html', {'bots': bots})


@login_required
def my_bots(request):
    """Render the user's personal bot collection."""
    user_bots = Bot.objects.filter(owner=request.user)
    return render(request, 'bots/my_bots.html', {'bots': user_bots})


@login_required
def create_bot(request):
    """Handle bot creation form and limit based on subscription."""
    try:
        user_profile = request.user.profile
    except UserProfile.DoesNotExist:
        user_profile = None

    bot_count = Bot.objects.filter(owner=request.user).count()

    if (not user_profile or not user_profile.is_subscribed) and bot_count >= 3:
        messages.error(
            request,
            "Free plan allows up to 3 bots. Upgrade to Premium for more."
        )
        return redirect('bots:my-bots')

    if request.method == 'POST':
        form = BotForm(request.POST)
        if form.is_valid():
            # Check for duplicate bot name
            duplicate_exists = Bot.objects.filter(
                owner=request.user,
                name=form.cleaned_data['name']
            ).exists()
            if duplicate_exists:
                messages.error(
                    request,
                    "You already have a bot with this name. Please choose a different name."
                )
                return render(request, 'bots/create_bot.html', {'form': form})

            bot = form.save(commit=False)
            bot.owner = request.user
            bot.save()
            messages.success(request, "Bot created successfully!")
            return redirect('bots:my-bots')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = BotForm()

    return render(request, 'bots/create_bot.html', {'form': form})


@login_required
def bot_chat_api(request, bot_id):
    """Return chat history for a given bot via JSON."""
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
    if request.method == 'GET':
        chat_messages = ChatMessage.objects.filter(
            bot=bot, user=request.user
        ).order_by('timestamp')
        data = [
            {'sender': m.sender, 'message': m.message}
            for m in chat_messages
        ]
        return JsonResponse({'messages': data})
    return HttpResponseNotAllowed(['GET'])


@login_required
def edit_bot(request, bot_id):
    """Allow a user to edit a bot they own."""
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)

    if request.method == 'POST':
        form = BotForm(request.POST, instance=bot)
        if form.is_valid():
            edited_bot = form.save(commit=False)
            edited_bot.owner = request.user
            edited_bot.save()
            messages.success(request, "Bot updated successfully!")
            return redirect('bots:list')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = BotForm(instance=bot)

    return render(request, 'bots/edit_bot.html', {'form': form})



@login_required
def delete_bot(request, bot_id):
    """Delete a bot after confirmation."""
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
    if request.method == 'POST':
        bot.delete()
        return redirect('bots:list')
    return render(request, 'bots/confirm_delete.html', {'bot': bot})


@login_required
@csrf_protect
def bot_chat_playground(request, bot_id):
    """Handle bot knowledge uploads and render chat playground."""
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
    knowledge_form = KnowledgeBaseForm()

    if request.method == 'POST':
        knowledge_form = KnowledgeBaseForm(request.POST, request.FILES)
        if knowledge_form.is_valid():
            manual_text = knowledge_form.cleaned_data.get('manual_text')
            file = knowledge_form.cleaned_data.get('file')
            knowledge = KnowledgeBase(
                bot=bot,
                uploaded_by=request.user,
                file=file if file else None
            )
            knowledge.save()

            try:
                text = manual_text if manual_text else extract_text(
                    knowledge.file.path, knowledge.file.name
                )

                KnowledgeChunk.objects.filter(
                    knowledge_file=knowledge
                ).delete()

                chunks = chunk_text(text)
                for chunk_text_part in chunks:
                    chunk = KnowledgeChunk.objects.create(
                        knowledge_file=knowledge,
                        text=chunk_text_part
                    )
                    embedding = generate_embedding(chunk.text)
                    chunk.embedding = embedding
                    chunk.save(update_fields=['embedding'])

                logger.info(
                    "Uploaded and processed {} chunks.".format(len(chunks))
                )
                messages.success(
                    request,
                    "✅ Your knowledge was uploaded and processed successfully!"
                )

            except Exception as e:
                logger.error(f"Error processing uploaded knowledge: {e}")
                messages.error(
                    request,
                    "⚠️ There was an error processing your input."
                )

            return redirect('bots:playground', bot_id=bot.id)
        else:
            messages.error(
                request,
                "⚠️ Please correct the errors below."
            )

    chat_messages = ChatMessage.objects.filter(
        bot=bot, user=request.user
    ).order_by('timestamp')

    return render(request, 'bots/playground.html', {
        'bot': bot,
        'chat_messages': chat_messages,
        'knowledge_form': knowledge_form,
    })


@login_required
@csrf_exempt
def ajax_chat(request, bot_id):
    """Process chat message, generate OpenAI reply, and return via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method.'}, status=405)

    try:
        bot = Bot.objects.get(id=bot_id, owner=request.user)
    except Bot.DoesNotExist:
        return JsonResponse(
            {'error': 'Bot not found or unauthorized.'}, status=404
        )

    try:
        data = json.loads(request.body.decode('utf-8'))
        user_input = data.get('message')

        if not user_input:
            return JsonResponse(
                {'error': 'No message provided.'}, status=400
            )

        ChatMessage.objects.create(
            bot=bot, user=request.user, sender='user', message=user_input
        )

        messages_qs = ChatMessage.objects.filter(
            bot=bot, user=request.user
        ).order_by('timestamp')

        history = [{'role': 'system', 'content': bot.personality}]
        for m in messages_qs:
            history.append({
                'role': 'user' if m.sender == 'user' else 'assistant',
                'content': m.message
            })

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=history
        )

        reply = response.choices[0].message['content']

        ChatMessage.objects.create(
            bot=bot, user=request.user, sender='assistant', message=reply
        )

        return JsonResponse({'reply': reply})

    except Exception:
        logger.error(f"ajax_chat error: {traceback.format_exc()}")
        return JsonResponse({'error': 'An error occurred.'}, status=500)


@login_required
def analytics_dashboard(request):
   """Display usage analytics for the current user's bots."""
    bots = Bot.objects.filter(owner=request.user)

    # Prepare bot message count data
    bot_data = {'labels': [], 'counts': []}
    for bot in bots:
        bot_data['labels'].append(bot.name)
        bot_data['counts'].append(
            ChatMessage.objects.filter(bot=bot, user=request.user).count()
        )

    # Prepare user message count data (only for current user)
    user_data = {'labels': [], 'counts': []}
    user_data['labels'].append(request.user.username)
    user_data['counts'].append(
        ChatMessage.objects.filter(user=request.user).count()
    )

    return render(request, 'bots/analytics_dashboard.html', {
        'bot_data': json.dumps(bot_data),
        'user_data': json.dumps(user_data),
    })


@staff_member_required
def admin_dashboard(request):
     """Admin-only dashboard showing all users and bots activity."""
    bots = Bot.objects.all()
    users = User.objects.all()

    bot_data = {'labels': [], 'counts': []}
    for bot in bots:
        bot_data['labels'].append(bot.name)
        bot_data['counts'].append(
            ChatMessage.objects.filter(bot=bot).count()
        )

    user_data = {'labels': [], 'counts': []}
    for user in users:
        user_data['labels'].append(user.username)
        user_data['counts'].append(
            ChatMessage.objects.filter(user=user).count()
        )

    return render(request, 'bots/analytics_dashboard.html', {
        'bot_data': json.dumps(bot_data),
        'user_data': json.dumps(user_data),
    })


@login_required
def discord_connect(request, pk):
    """Handle GET requests for connecting a Discord bot."""
    if request.method == 'GET':
        token = request.GET.get("token")
        if not token:
            return JsonResponse({"error": "Missing bot token."}, status=400)
        return JsonResponse(
            {
                "message": "Bot connection request received.",
                "bot_id": pk,
                "token": token,
            }
        )
    return JsonResponse({"error": "Only GET requests allowed."}, status=405)
