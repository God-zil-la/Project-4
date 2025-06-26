from django.contrib.auth import get_user_model, login
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .tokens import account_activation_token
from bots.models import Bot  # Make sure this import matches your app structure

User = get_user_model()

@login_required
def bot_list(request):
    """
    List bots belonging to the logged-in user only.
    """
    user_bots = Bot.objects.filter(owner=request.user)
    return render(request, 'bots/bot_list.html', {'bots': user_bots})

@login_required
def index(request):
    """
    Simple index/dashboard view for logged-in users.
    """
    return render(request, 'accounts/index.html')

def register(request):
    """
    Handle new user registration and send activation email.
    """
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists. Please choose another.")
            return render(request, 'accounts/register.html')

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered. Try logging in.")
            return render(request, 'accounts/register.html')

        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_active = False
        user.save()

        current_site = get_current_site(request)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)
        activation_path = reverse('accounts:activate', kwargs={'uidb64': uid, 'token': token})
        activation_link = f"https://{current_site.domain}{activation_path}"

        context = {
            'user': user,
            'domain': current_site.domain,
            'uid': uid,
            'token': token,
            'protocol': 'https',
            'activation_link': activation_link,
        }

        try:
            text_content = render_to_string('accounts/activation_email.txt', context)
            html_content = render_to_string('accounts/activation_email.html', context)
            email = EmailMultiAlternatives(
                subject='Activate your AI Assistant account.',
                body=text_content,
                to=[email]
            )
            email.attach_alternative(html_content, "text/html")
            email.send()
        except Exception:
            messages.error(request, "Failed to send activation email. Please try again later.")
            user.delete()  # Remove user if email sending failed
            return render(request, 'accounts/register.html')

        messages.success(request, "Registration successful! Check your email to activate your account.")
        return redirect('accounts:login')

    return render(request, 'accounts/register.html')

def activate(request, uidb64, token):
    """
    Activate user account via link with uidb64 and token.
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and account_activation_token.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        messages.success(request, "Your account has been activated! You are now logged in.")
        return redirect('accounts:index')

    messages.error(request, "Activation link is invalid or expired.")
    return redirect('accounts:register')
