from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import PasswordResetForm
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse


class RegisterForm(forms.ModelForm):
    """User registration form with password confirmation and validation."""

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
        """Validate that the two password fields match."""
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords do not match.")
        return password2

    def save(self, commit=True):
        """Save the user with a hashed password."""
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class CustomPasswordResetForm(PasswordResetForm):
    """Keep Django's secure tokens and eligible-user filtering."""

    def save(self, **kwargs):
        from urllib.parse import urlsplit
        from .email_utils import public_origin
        origin = urlsplit(public_origin(kwargs.get("request")))
        kwargs["domain_override"] = origin.netloc
        kwargs["use_https"] = origin.scheme == "https"
        return super().save(**kwargs)

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        from django.db import transaction
        from .email_utils import send_account_email
        context = dict(context)
        context["site_name"] = "AI Assistant"
        context["reset_url"] = "{}://{}{}".format(
            context["protocol"], context["domain"], reverse(
                "accounts:password_reset_confirm",
                kwargs={"uidb64": context["uid"], "token": context["token"]}))
        subject = "".join(render_to_string(subject_template_name, context).splitlines())
        message = EmailMultiAlternatives(subject, render_to_string(email_template_name, context),
                                         from_email, [to_email])
        if html_email_template_name:
            message.attach_alternative(render_to_string(html_email_template_name, context), "text/html")
        transaction.on_commit(lambda: send_account_email(message))
