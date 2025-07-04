from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordResetForm
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.contrib.sites.shortcuts import get_current_site
from django.urls import reverse

# ✅ RegisterForm with password confirmation
class RegisterForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'})
    )
    password2 = forms.CharField(
        label="Confirm Password",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        strip=False
    )

    class Meta:
        model = User
        fields = ['username', 'email']

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords do not match.")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


# ✅ CustomPasswordResetForm with reset_url pre-rendered
class CustomPasswordResetForm(PasswordResetForm):
    def send_mail(self, subject_template_name, email_template_name,
                  context, from_email, to_email, html_email_template_name=None):
        subject = render_to_string(subject_template_name, context).strip()
        body = render_to_string(email_template_name, context)

        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name:
            html_email = render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, 'text/html')

        email_message.send()

    def save(self, domain_override=None,
             subject_template_name='accounts/password_reset_subject.txt',
             email_template_name='accounts/password_reset_email.txt',
             use_https=False, token_generator=None,
             from_email=None, request=None, html_email_template_name='accounts/password_reset_email.html',
             extra_email_context=None):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        from django.contrib.auth import get_user_model

        UserModel = get_user_model()
        email = self.cleaned_data["email"]
        active_users = UserModel._default_manager.filter(email__iexact=email, is_active=True)

        if not active_users:
            return

        for user in active_users:
            if not domain_override and request:
                current_site = get_current_site(request)
                site_name = current_site.name
                domain = current_site.domain
            else:
                site_name = domain = domain_override or getattr(settings, 'DEFAULT_DOMAIN', 'example.com')

            # ✅ Build the full reset URL here
            uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
            token = (token_generator or default_token_generator).make_token(user)
            reset_path = reverse('accounts:password_reset_confirm', kwargs={'uidb64': uidb64, 'token': token})
            reset_url = f"{'https' if use_https else 'http'}://{domain}{reset_path}"

            context = {
                'email': email,
                'domain': domain,
                'site_name': site_name,
                'user': user,
                'protocol': 'https' if use_https else 'http',
                'request': request,
                'reset_url': reset_url,
            }

            if extra_email_context:
                context.update(extra_email_context)

            self.send_mail(
                subject_template_name, email_template_name, context,
                from_email or settings.DEFAULT_FROM_EMAIL, email,
                html_email_template_name=html_email_template_name
            )
