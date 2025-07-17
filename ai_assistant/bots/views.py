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
from django.views.decorators.csrf import csrf_protect
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
    logger.info("bot_list view called")
    bots = Bot.objects.filter(owner=request.user)
    return render(request, 'bots/bot_list.html', {'bots': bots})


@login_required
def my_bots(request):
    user_bots = Bot.objects.filter(owner=request.user)
    return render(request, 'bots/my_bots.html', {'bots': user_bots})


@login_required
def create_bot(request):
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
            bot = form.save(commit=False)
            bot.owner = request.user
            bot.save()
            messages.success(request, "Bot created successfully!")
            return redirect('bots:my-bots')
    else:
        form = BotForm()

    return render(request, 'bots/create_bot.html', {'form': form})


@login_required
def bot_chat_api(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
    if request.method == 'GET':
        chat_messages = ChatMessage.objects.filter(
            bot=bot,
            user=request.user
        ).order_by('timestamp')
        data = [
            {'sender': m.sender, 'message': m.message}
            for m in chat_messages
        ]
        return JsonResponse({'messages': data})
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
@csrf_protect
def bot_chat_playground(request, bot_id):
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
                if manual_text:
                    text = manual_text
                else:
                    text = extract_text(
                        knowledge.file.path,
                        knowledge.file.name
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
        bot=bot,
        user=request.user
    ).order_by('timestamp')

    return render(request, 'bots/playground.html', {
        'bot': bot,
        'chat_messages': chat_messages,
        'knowledge_form': knowledge_form,
    })
