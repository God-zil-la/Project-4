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

        # Validation
        if not username or not email or not password or not password2:
            messages.error(request, "All fields are required.")
            return render(request, 'accounts/register.html', {
                'username': username,
                'email': email,
            })

        if password != password2:
            messages.error(request, "Passwords do not match.")
            return render(request, 'accounts/register.html', {
                'username': username,
                'email': email,
            })

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists. Please choose another.")
            return render(request, 'accounts/register.html', {
                'username': username,
                'email': email,
            })

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered. Try logging in.")
            return render(request, 'accounts/register.html', {
                'username': username,
                'email': email,
            })

        # Create inactive user
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_active = False
        user.save()

        # Generate activation link with correct protocol
        current_site = get_current_site(request)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)

        protocol = 'https' if not settings.DEBUG else 'http'
        activation_link = f"{protocol}://{current_site.domain}{reverse('accounts:activate', kwargs={'uidb64': uid, 'token': token})}"

        context = {
            'user': user,
            'domain': current_site.domain,
            'uid': uid,
            'token': token,
            'protocol': protocol,
            'activation_link': activation_link,
        }

        # Send activation email
        text_content = render_to_string('accounts/activation_email.txt', context)
        html_content = render_to_string('accounts/activation_email.html', context)

        email_message = EmailMultiAlternatives(
            subject='Activate your AI Assistant account.',
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[email]
        )
        email_message.attach_alternative(html_content, "text/html")
        email_message.send()

        # Show success page
        return render(request, 'accounts/activation_sent.html')

    # If GET request
    return render(request, 'accounts/register.html', {
        'username': '',
        'email': '',
    })


def activate(request, uidb64, token):
    print("Activation view called")
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        print(f"Decoded UID: {uid}")
        user = User.objects.get(pk=uid)
        print(f"User found: {user.username}")
    except (TypeError, ValueError, OverflowError, User.DoesNotExist) as e:
        user = None
        print(f"User lookup failed: {e}")

    if user is not None:
        valid_token = account_activation_token.check_token(user, token)
        print(f"Token valid: {valid_token}")
    else:
        print("No user to validate token")

    if user is not None and valid_token:
        user.is_active = True
        user.save()
        login(request, user)
        print("User activated and logged in")
        return render(request, 'accounts/activation_success.html')
    else:
        print("Activation failed - invalid token or user")
        return render(request, 'accounts/activation_invalid.html')

