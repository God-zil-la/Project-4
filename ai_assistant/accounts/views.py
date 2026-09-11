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
from django.db import transaction
from .email_utils import public_origin, send_account_email
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password


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
    """Register a new user and send an email verification link."""
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

        if User.objects.filter(email__iexact=email).exists():
            messages.error(
                request,
                "An account with this email address already exists."
            )
            return render(
                request,
                'accounts/register.html',
                {'username': username, 'email': email}
            )

        try:
            validate_email(email)
            validate_password(
                password,
                User(username=username, email=email)
            )
        except ValidationError as exc:
            for error in exc.messages:
                messages.error(request, error)

            return render(
                request,
                'accounts/register.html',
                {'username': username, 'email': email}
            )

        origin = public_origin(request)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        # The account stays inactive until the email address is verified.
        user.is_active = False
        user.save(update_fields=['is_active'])

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)

        activation_path = reverse(
            'accounts:activate',
            kwargs={
                'uidb64': uid,
                'token': token,
            }
        )

        activation_url = f"{origin}{activation_path}"

        context = {
            'user': user,
            'domain': origin.split('://', 1)[1],
            'activation_url': activation_url,
        }

        subject = "Verify your email - AI Assistant"

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
        email_message.attach_alternative(
            html_content,
            "text/html"
        )

        transaction.on_commit(
            lambda: send_account_email(email_message)
        )

        return render(
            request,
            'accounts/activation_sent.html',
            {'email': email}
        )

    return render(
        request,
        'accounts/register.html',
        {'username': '', 'email': ''}
    )

def resend_activation(request):
    """Resend the email verification link for an inactive account."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()

        try:
            user = User.objects.get(
                email__iexact=email,
                is_active=False
            )
        except User.DoesNotExist:
            user = None

        if user is not None:
            origin = public_origin(request)

            uid = urlsafe_base64_encode(
                force_bytes(user.pk)
            )
            token = account_activation_token.make_token(user)

            activation_path = reverse(
                'accounts:activate',
                kwargs={
                    'uidb64': uid,
                    'token': token,
                }
            )

            activation_url = f"{origin}{activation_path}"

            context = {
                'user': user,
                'domain': origin.split('://', 1)[1],
                'activation_url': activation_url,
            }

            subject = "Verify your email - AI Assistant"

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
                [user.email]
            )

            email_message.attach_alternative(
                html_content,
                "text/html"
            )

            transaction.on_commit(
                lambda: send_account_email(email_message)
            )

        messages.success(
            request,
            "If an unverified account exists with that email address, "
            "a new verification email has been sent."
        )

        return redirect('accounts:login')

    return render(
        request,
        'accounts/resend_activation.html'
    )


def activate(request, uidb64, token):
    """Activate a user account via the email verification link."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None:
        return render(
            request,
            'accounts/activation_invalid.html'
        )

    if user.is_active:
        return render(
            request,
            'accounts/activation_already_active.html'
        )

    if account_activation_token.check_token(user, token):
        user.is_active = True
        user.save(update_fields=['is_active'])

        origin = public_origin(request)
        dashboard_url = f"{origin}{reverse('dashboard:home')}"

        context = {
            'user': user,
            'dashboard_url': dashboard_url,
        }

        subject = "Your email is verified 🎉"

        text_content = render_to_string(
            'accounts/welcome_email.txt',
            context
        )

        html_content = render_to_string(
            'accounts/welcome_email.html',
            context
        )

        email_message = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [user.email]
        )

        email_message.attach_alternative(
            html_content,
            "text/html"
        )

        transaction.on_commit(
            lambda: send_account_email(email_message)
        )

        login(request, user)

        return render(
            request,
            'accounts/activation_success.html'
        )

    return render(
        request,
        'accounts/activation_invalid.html'
    )