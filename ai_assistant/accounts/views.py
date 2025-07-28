from django.contrib.auth import get_user_model, login
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.decorators import login_required

from ai_assistant.bots.models import Bot
from .tokens import account_activation_token


User = get_user_model()

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from ai_assistant.bots.models import Bot
from ai_assistant.bots.forms import BotForm


@login_required
def bot_list(request):
    """Display a list of bots owned by the logged-in user."""
    bots = Bot.objects.filter(owner=request.user)
    return render(request, 'bots/bot_list.html', {'bots': bots})


@login_required
def create_bot(request):
    """Handle bot creation form for the logged-in user."""
    if request.method == 'POST':
        form = BotForm(request.POST, user=request.user)
        if form.is_valid():
            name = form.cleaned_data['name']
            if Bot.objects.filter(name__iexact=name, owner=request.user).exists():
                form.add_error('name', "A bot with this name already exists.")
            else:
                bot = form.save(commit=False)
                bot.owner = request.user
                bot.save()
                messages.success(request, "Bot created successfully!")
                return redirect('bots:list')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = BotForm(user=request.user)
    return render(request, 'bots/create_bot.html', {'form': form})


@login_required
def edit_bot(request, bot_id):
    """Allow editing of an existing bot owned by the user."""
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
    if request.method == 'POST':
        form = BotForm(request.POST, instance=bot, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Bot updated successfully!")
            return redirect('bots:list')
        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = BotForm(instance=bot, user=request.user)
    return render(request, 'bots/edit_bot.html', {'form': form})


@login_required
def delete_bot(request, bot_id):
    """Confirm and process bot deletion for the logged-in user."""
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
    if request.method == 'POST':
        bot.delete()
        messages.success(request, "Bot deleted successfully.")
        return redirect('bots:list')
    return render(request, 'bots/confirm_delete.html', {'bot': bot})



def register(request):
    """Handle user registration, validation, and welcome email."""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        if not all([username, email, password, password2]):
            messages.error(request, "All fields are required.")
            return render(
                request,
                'accounts/register.html',
                {'username': username, 'email': email}
            )

        if password != password2:
            messages.error(request, "Passwords do not match.")
            return render(
                request,
                'accounts/register.html',
                {'username': username, 'email': email}
            )

        if User.objects.filter(username=username).exists():
            messages.error(
                request,
                "Username already exists. Please choose another."
            )
            return render(
                request,
                'accounts/register.html',
                {'username': username, 'email': email}
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        user.is_active = True
        user.save()

        context = {
            'user': user,
            'domain': get_current_site(request).domain,
        }
        subject = (
            "Welcome to AI Assistant - "
            "Your account is active!"
        )
        text_content = render_to_string(
            'accounts/activation_email.txt',
            context
        )
        html_content = render_to_string(
            'accounts/activation_email.html',
            context
        )

        email_message = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [email]
        )
        email_message.attach_alternative(html_content, "text/html")
        email_message.send()

        return render(request, 'accounts/activation_sent.html')

    return render(
        request,
        'accounts/register.html',
        {'username': '', 'email': ''}
    )


def activate(request, uidb64, token):
    """Activate user account via email confirmation link."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        if not user.is_active:
            user.is_active = True
            user.save()
            login(request, user)
            return render(request, 'accounts/activation_success.html')
        else:
            return render(request, 'accounts/activation_already_active.html')
    else:
        return render(request, 'accounts/activation_invalid.html')
