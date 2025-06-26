from django.contrib.auth import get_user_model, login
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import EmailMultiAlternatives
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib import messages
from django.urls import reverse

from .tokens import account_activation_token
from django.contrib.auth.decorators import login_required

# Use the custom user model or default User
User = get_user_model()

@login_required
def index(request):
    # Simple authenticated page example
    return render(request, 'accounts/index.html')

def register(request):
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

        url_path = reverse('accounts:activate', kwargs={'uidb64': uid, 'token': token})
        print(f"[DEBUG] URL path: {url_path!r}")

        activation_link = f"https://{current_site.domain}{url_path}"
        activation_link = activation_link.rstrip('"\'' )  # strip trailing quotes if any
        print(f"[DEBUG] Activation link: {activation_link!r}")

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
            to=[email]
        )
        email_message.attach_alternative(html_content, "text/html")
        email_message.send()

        return render(request, 'accounts/activation_sent.html')

    return render(request, 'accounts/register.html')


def activate(request, uidb64, token):
    try:
        # Decode uid from base64 to get user ID
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    # Check token validity and user existence
    if user is not None and account_activation_token.check_token(user, token):
        # Activate user and log them in
        user.is_active = True
        user.save()
        login(request, user)
        return render(request, 'accounts/activation_success.html')
    else:
        # Invalid activation link
        return render(request, 'accounts/activation_invalid.html')
