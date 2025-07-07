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

@login_required
def index(request):
    return render(request, 'accounts/index.html')

@login_required
def bot_list(request):
    user_bots = Bot.objects.filter(owner=request.user)
    return render(request, 'bots/bot_list.html', {'bots': user_bots})

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        if not all([username, email, password, password2]):
            messages.error(request, "All fields are required.")
            return render(request, 'accounts/register.html', {'username': username, 'email': email})

        if password != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, 'accounts/register.html', {'username': username, 'email': email})

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists. Please choose another.")
            return render(request, 'accounts/register.html', {'username': username, 'email': email})

        
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_active = True
        user.save()

        
        context = {
            'user': user,
            'domain': get_current_site(request).domain,
        }
        subject = "Welcome to AI Assistant - Your account is active!"
        text_content = render_to_string('accounts/activation_email.txt', context)
        html_content = render_to_string('accounts/activation_email.html', context)

        email_message = EmailMultiAlternatives(subject, text_content, settings.DEFAULT_FROM_EMAIL, [email])
        email_message.attach_alternative(html_content, "text/html")
        email_message.send()

        return render(request, 'accounts/activation_sent.html')

    return render(request, 'accounts/register.html', {'username': '', 'email': ''})


def activate(request, uidb64, token):
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