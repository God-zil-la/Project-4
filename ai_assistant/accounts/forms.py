# ai_assistant/accounts/forms.py

from django.contrib.auth.forms import PasswordResetForm
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site

class CustomPasswordResetForm(PasswordResetForm):
    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        # ... [your current send_mail code here] ...

    def save(self, domain_override=None,
             subject_template_name='registration/password_reset_subject.txt',
             email_template_name='registration/password_reset_email.txt',
             use_https=False, token_generator=None,
             from_email=None, request=None, html_email_template_name=None,
             extra_email_context=None):
        """
        Generates a one-use only link for resetting password and sends to the user.
        """
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.contrib.auth import get_user_model

        email = self.cleaned_data["email"]
        UserModel = get_user_model()
        active_users = UserModel._default_manager.filter(email__iexact=email, is_active=True)
        for user in active_users:
            context = {
                'email': email,
                'domain': domain_override or getattr(settings, 'DEFAULT_DOMAIN'),
                'site_name': domain_override or getattr(settings, 'DEFAULT_DOMAIN'),
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'user': user,
                'token': (token_generator or default_token_generator).make_token(user),
                'protocol': 'https' if use_https else 'http',
                'request': request,
            }
            if extra_email_context:
                context.update(extra_email_context)

            self.send_mail(
                subject_template_name, email_template_name, context,
                from_email or settings.DEFAULT_FROM_EMAIL, email,
                html_email_template_name=html_email_template_name
            )
