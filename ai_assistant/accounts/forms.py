# ai_assistant/accounts/forms.py

from django.contrib.auth.forms import PasswordResetForm
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site

class CustomPasswordResetForm(PasswordResetForm):
    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        # Override the domain and protocol explicitly for email links
        request = context.get('request')
        if request:
            current_site = get_current_site(request)
            domain = current_site.domain
            protocol = 'https' if request.is_secure() else 'http'
        else:
            # fallback if no request in context
            domain = getattr(settings, 'DEFAULT_DOMAIN', 'example.com')
            protocol = getattr(settings, 'DEFAULT_PROTOCOL', 'https')

        # Add site_name for your template
        context['domain'] = domain
        context['protocol'] = protocol
        context['site_name'] = domain  

        # Render subject & body from your templates
        subject = render_to_string(subject_template_name, context)
        subject = ''.join(subject.splitlines())  

        body = render_to_string(email_template_name, context)

        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name:
            html_email = render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, 'text/html')

        email_message.send()
