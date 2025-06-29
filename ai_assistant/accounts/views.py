from django.contrib.auth import get_user_model, login
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.shortcuts import render, redirect
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
        password_confirm = request.POST.get('password_confirm', '')

        # Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists. Please choose another.")
            return render(request, 'accounts/register.html', {
                'username': username,
                'email': email,
            })

        # Check if email exists
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered. Try logging in.")
            return render(request, 'accounts/register.html', {
                'username': username,
            })

        # Check if passwords match
        if password != password_confirm:
            messages.error(request, "Passwords do not match. Please try again.")
            return render(request, 'accounts/register.html', {
                'username': username,
                'email': email,
            })

        # Create inactive user
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_active = False
        user.save()
        user.refresh_from_db()

        # Generate activation link
        current_site = get_current_site(request)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)

        try:
            url_path = reverse('accounts:activate', kwargs={'uidb64': uid, 'token': token})
        except Exception as e:
            messages.error(request, f"URL generation failed: {e}")
            return render(request, 'accounts/register.html')

        activation_link = f"https://{current_site.domain}{url_path}"

        context = {
            'user': user,
            'domain': current_site.domain,
            'uid': uid,
            'token': token,
            'protocol': 'https',
            'activation_link': activation_link,
        }

        text_content = render_to_string('accounts/activation_email.txt', context)
        html_content = render_to_string('accounts/activation_email.html', context)

        email_message = EmailMultiAlternatives(
            subject='Activate your AI Assistant account.',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email]
        )
        email_message.attach_alternative(html_content, "text/html")

        try:
            email_message.send()
        except Exception as e:
            messages.error(request, f"⚠️ Email sending failed: {e}")
            return render(request, 'accounts/register.html')

        return render(request, 'accounts/activation_sent.html')

    # GET request
    return render(request, 'accounts/register.html')

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return render(request, 'accounts/activation_success.html')
    else:
        return render(request, 'accounts/activation_invalid.html')
