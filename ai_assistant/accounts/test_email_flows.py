import re
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .email_utils import public_origin


@override_settings(PUBLIC_BASE_URL="https://accounts.example.org")
class AccountEmailTests(TestCase):
    def register(self):
        return self.client.post(
            reverse("accounts:register"),
            {
                "username": "newuser",
                "email": "new@example.org",
                "password": "Strong-test-password-194!",
                "password2": "Strong-test-password-194!",
            },
        )

    def reset(self, email="member@example.org"):
        return self.client.post(
            reverse("accounts:password_reset"),
            {"email": email},
        )

    def member(self):
        return User.objects.create_user(
            "member",
            "member@example.org",
            "Old-password-123!",
        )

    def reset_link(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.reset().status_code, 302)

        return re.search(
            r"https://accounts.example.org/\S+",
            mail.outbox[-1].body,
        ).group()

    def test_registration_sends_verification_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.register()
            self.assertEqual(len(mail.outbox), 0)

        self.assertContains(response, "Check Your Email")

        user = User.objects.get(username="newuser")
        self.assertFalse(user.is_active)

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["new@example.org"])

        self.assertIn(
            "https://accounts.example.org/",
            mail.outbox[0].body,
        )

    def test_registration_delivery_failure_keeps_generic_response(self):
        with patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=RuntimeError("private"),
        ), self.captureOnCommitCallbacks(execute=True):
            response = self.register()

        self.assertContains(response, "Check Your Email")
        self.assertNotContains(response, "private")

        user = User.objects.get(username="newuser")
        self.assertFalse(user.is_active)

    def test_zero_delivery_is_logged(self):
        with patch(
            "django.core.mail.EmailMultiAlternatives.send",
            return_value=0,
        ), self.assertLogs(
            "ai_assistant.accounts.email_utils",
            level="ERROR",
        ), self.captureOnCommitCallbacks(execute=True):
            self.register()

    def test_duplicate_registration_does_not_send_again(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.register()
            self.register()

        self.assertEqual(len(mail.outbox), 1)

    def test_registration_rejects_invalid_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse("accounts:register"),
                {
                    "username": "invalid",
                    "email": "not-an-email",
                    "password": "Strong-password-789!",
                    "password2": "Strong-password-789!",
                },
            )

        self.assertContains(
            response,
            "Enter a valid email address",
        )
        self.assertFalse(
            User.objects.filter(username="invalid").exists()
        )
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(DEBUG=False)
    def test_reset_production_url_ignores_request_scheme_and_sites(self):
        self.member()

        self.assertTrue(
            self.reset_link().startswith(
                "https://accounts.example.org/"
            )
        )

    def test_password_reset_end_to_end_and_used_token(self):
        user = self.member()
        link = self.reset_link()

        self.assertIn(
            link,
            mail.outbox[0].alternatives[0].content,
        )

        response = self.client.get(link)

        self.assertEqual(response.status_code, 302)

        form_url = response.url

        self.assertTrue(
            self.client.get(form_url).context["validlink"]
        )

        response = self.client.post(
            form_url,
            {
                "new_password1": "New-complex-password-789!",
                "new_password2": "New-complex-password-789!",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:password_reset_complete"),
        )

        user.refresh_from_db()

        self.assertTrue(
            user.check_password(
                "New-complex-password-789!"
            )
        )

        self.assertFalse(
            self.client.get(
                link,
                follow=True,
            ).context["validlink"]
        )

        self.assertFalse(
            self.client.get(
                form_url,
            ).context["validlink"]
        )

    def test_invalid_token(self):
        response = self.client.get(
            reverse(
                "accounts:password_reset_confirm",
                kwargs={
                    "uidb64": "MQ",
                    "token": "invalid",
                },
            )
        )

        self.assertFalse(
            response.context["validlink"]
        )

    def test_expired_token(self):
        self.member()

        with patch.object(
            default_token_generator,
            "_now",
            return_value=timezone.now().replace(
                tzinfo=None
            ) - timedelta(hours=2),
        ):
            link = self.reset_link()

        self.assertFalse(
            self.client.get(
                link,
                follow=True,
            ).context["validlink"]
        )

    def test_unknown_inactive_and_unusable_accounts_send_nothing(self):
        user = self.member()
        user.set_unusable_password()
        user.save()

        User.objects.create_user(
            "inactive",
            "inactive@example.org",
            "password",
            is_active=False,
        )

        for email in [
            user.email,
            "inactive@example.org",
            "missing@example.org",
        ]:
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(
                    self.reset(email).status_code,
                    302,
                )

        self.assertEqual(len(mail.outbox), 0)

    def test_reset_delivery_failure_keeps_generic_response(self):
        self.member()

        with patch(
            "django.core.mail.EmailMultiAlternatives.send",
            side_effect=RuntimeError("secret"),
        ), self.captureOnCommitCallbacks(execute=True):
            response = self.reset()

        self.assertEqual(response.status_code, 302)

        page = self.client.get(response.url)

        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "secret")
        self.assertContains(page, "Reset Your Password")

    def test_rollback_discards_email_callback(self):
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    self.register()
                    raise RuntimeError()
            except RuntimeError:
                pass

        self.assertEqual(len(mail.outbox), 0)

        self.assertFalse(
            User.objects.filter(
                username="newuser",
            ).exists()
        )

    @override_settings(DEBUG=False)
    def test_production_origin_requires_https_and_explicit_domain(self):
        for origin in [
            "",
            "http://example.org",
            "https://example.org/path",
            "https://user:pass@example.org",
            "https://example.org?query=1",
        ]:
            with self.settings(
                PUBLIC_BASE_URL=origin
            ), self.assertRaises(
                ImproperlyConfigured
            ):
                public_origin()

        self.assertEqual(
            public_origin(),
            "https://accounts.example.org",
        )