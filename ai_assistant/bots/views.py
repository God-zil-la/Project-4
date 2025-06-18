from openai import OpenAI
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse
import json
from django.conf import settings
from .models import Bot, ChatMessage
from .forms import BotForm
from ai_assistant.buildabot import settings
import os


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


@staff_member_required
def admin_dashboard(request):
    users = User.objects.all()
    bots = Bot.objects.all()
    messages = ChatMessage.objects.order_by('-timestamp')[:50]
    return render(request, 'bots/admin_dashboard.html', {
        'users': users,
        'bots': bots,
        'messages': messages,
    })


@login_required
@csrf_protect
def ajax_chat(request, bot_id):
    if request.method == 'POST':
        data = json.loads(request.body)
        user_message = data.get('message')
        bot = get_object_or_404(Bot, id=bot_id)

        # Save user message
        ChatMessage.objects.create(
            bot=bot,
            user=request.user,
            message=user_message,
            sender='user'
        )

        # System prompt
        category_prompt = {
            "general": "You are a helpful assistant who answers clearly and briefly.",
            "fitness": "You are a fitness coach. Give motivating, accurate health advice.",
            "finance": "You are a financial expert. Explain money, budgeting, and investment tips.",
            "funny": "You are a stand-up comedian. Always respond with jokes and humor.",
            "support": "You are a kind, supportive friend. Be empathetic and comforting.",
            "tech": "You are a tech specialist. Explain technology in simple terms.",
        }.get(bot.category, "You are a helpful assistant.")

        personality = bot.personality or "friendly and professional"

        system_message = f"{category_prompt} Your tone should be '{personality}'."

        try:
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ]
            )
            bot_response = response.choices[0].message.content.strip()
        except Exception as e:
            print("❌ OpenAI API error:", e)
            bot_response = f"[API Error] {str(e)}"

        ChatMessage.objects.create(
            bot=bot,
            user=request.user,
            message=bot_response,
            sender='bot'
        )

        return JsonResponse({'response': bot_response})



@login_required
def bot_list(request):
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
            print("Form errors:", form.errors)  # ✅ DEBUG
    else:
        form = BotForm()
    
    return render(request, 'bots/create_bot.html', {'form': form})



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
    return render(request, 'bots/playground.html', {
        'bot': bot,
        'messages': messages
    })


@login_required
def bot_chat_api(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)

    if request.method == 'POST':
        user_msg = request.POST.get('message')
        if user_msg:
            ChatMessage.objects.create(bot=bot, user=request.user, message=user_msg, sender='user')
            bot_reply = f"You said: {user_msg}"
            ChatMessage.objects.create(bot=bot, user=request.user, message=bot_reply, sender='bot')
            return JsonResponse({'reply': bot_reply})

    elif request.method == 'GET':
        messages = ChatMessage.objects.filter(bot=bot, user=request.user).order_by('timestamp')
        data = [{'sender': m.sender, 'message': m.message} for m in messages]
        return JsonResponse({'messages': data})
    