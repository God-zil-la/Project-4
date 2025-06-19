from ai_assistant.accounts.models import UserProfile
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse, HttpResponseNotAllowed
import json
import time
import os
from openai import OpenAI
from dotenv import load_dotenv
from .models import Bot, ChatMessage
from .forms import BotForm

load_dotenv()
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
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    data = json.loads(request.body)
    user_message = data.get('message')
    bot = get_object_or_404(Bot, id=bot_id)

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.reset_daily_count()

    if not profile.is_subscribed and profile.daily_message_count >= 20:  # or your limit
        return JsonResponse(
            {'response': "⚠️ Daily limit reached. Please subscribe to continue chatting."},
            status=429
        )

    ChatMessage.objects.create(bot=bot, user=request.user, message=user_message, sender='user')

    category_prompt = {
        "general": "You are a helpful assistant who answers clearly and concisely.",
        "fitness": "You are a fitness coach giving motivating, accurate health advice.",
        "finance": "You are a financial expert explaining money, budgeting, and investment tips.",
        "funny": "You are a stand-up comedian who always responds with jokes and humor.",
        "support": "You are a kind, supportive friend who is empathetic and comforting.",
        "tech": "You are a tech specialist explaining technology simply and clearly.",
    }.get(bot.category, "You are a helpful assistant.")

    # Use only category prompt as system message, ignoring custom personality
    system_message = category_prompt

    # Call OpenAI
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
                print("❌ OpenAI API error:", e)
                bot_response = f"[API Error] {str(e)}"
                break

    ChatMessage.objects.create(bot=bot, user=request.user, message=bot_response, sender='bot')

    profile.increment_message_count()

    return JsonResponse({'response': bot_response})



@login_required
def bot_chat_api(request, bot_id):
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)

    if request.method == 'GET':
        messages = ChatMessage.objects.filter(bot=bot, user=request.user).order_by('timestamp')
        return JsonResponse({'messages': [{'sender': m.sender, 'message': m.message} for m in messages]})

    return HttpResponseNotAllowed(['GET'])


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
