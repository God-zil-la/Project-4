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
        # Grab form data safely with .get()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')

        # Validation: Check if username exists
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists. Please choose another.")
            return render(request, 'accounts/register.html')

        # Validation: Check if email exists
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered. Try logging in.")
            return render(request, 'accounts/register.html')

        # Create inactive user (needs activation)
        user = User.objects.create_user(username=username, email=email, password=password)
        user.is_active = False  # User can't login until activated
        user.save()

        # Generate activation URL
        current_site = get_current_site(request)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = account_activation_token.make_token(user)

        # Build full activation link (absolute URL)
        activation_link = f"https://{current_site.domain}{reverse('accounts:activate', kwargs={'uidb64': uid, 'token': token})}"

        # Email context passed to templates
        context = {
            'user': user,
            'domain': current_site.domain,
            'uid': uid,
            'token': token,
            'protocol': 'https',  # Adjust if using http
            'activation_link': activation_link,  # FULL absolute URL for email
        }

        # Render email contents (plain text and HTML)
        text_content = render_to_string('accounts/activation_email.txt', context)
        html_content = render_to_string('accounts/activation_email.html', context)

        # Prepare email message with alternatives (text + HTML)
        email_message = EmailMultiAlternatives(
            subject='Activate your AI Assistant account.',
            body=text_content,
            to=[email]
        )
        email_message.attach_alternative(html_content, "text/html")
        email_message.send()

        # Show a confirmation page telling user to check email
        return render(request, 'accounts/activation_sent.html')

    # For GET requests just show the registration form
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
