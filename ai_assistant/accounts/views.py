from django.contrib.auth.models import User
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import EmailMessage
from django.shortcuts import render, redirect
from django.contrib import messages
from .tokens import account_activation_token
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login
from django.contrib.auth import get_user_model

User = get_user_model()

@login_required
def index(request):
    return render(request, 'accounts/index.html')


def register(request):
    if request.method == 'POST':
        username = request.POST['username']
        email = request.POST['email']
        password = request.POST['password']

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
        mail_subject = 'Activate your AI Assistant account.'
        message = render_to_string('accounts/activation_email.html', {
            'user': user,
            'domain': current_site.domain,
            'uid': urlsafe_base64_encode(force_bytes(user.pk)),
            'token': account_activation_token.make_token(user),
        }, request=request)

        email_message = EmailMessage(mail_subject, message, to=[email])
        email_message.send()

        return render(request, 'accounts/activation_sent.html')

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
