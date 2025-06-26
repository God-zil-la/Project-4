# ai_assistant/accounts/forms.py

from django.contrib.auth.forms import PasswordResetForm
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

class CustomPasswordResetForm(PasswordResetForm):
    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        
        # Force the correct domain and protocol
        context["domain"] = settings.DEFAULT_DOMAIN
        context["protocol"] = settings.DEFAULT_PROTOCOL

        subject = render_to_string(subject_template_name, context).strip()
        body = render_to_string(email_template_name, context)

        email = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name:
            html_email = render_to_string(html_email_template_name, context)
            email.attach_alternative(html_email, 'text/html')
        email.send()
