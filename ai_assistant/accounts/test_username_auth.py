"""Regression coverage for the public username login and registration routes."""
import re
from unittest.mock import patch

from django.contrib.auth import BACKEND_SESSION_KEY, SESSION_KEY
from django.contrib.auth.models import User
from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse

from .forms import RegisterForm


@override_settings(PUBLIC_BASE_URL="https://accounts.example.org")
class UsernameAuthTests(TestCase):
    password = "Strong-Test-Password-194!"
    variants = ("Funcy92", "funcy92", "FUNCY92", "FuNcY92")

    def setUp(self):
        self.user = User.objects.create_user(
            "Funcy92", "member@example.org", self.password,
        )

    def login(self, username, password=None):
        return self.client.post(reverse("accounts:login"), {
            "username": username,
            "password": self.password if password is None else password,
        })

    def register(self, username, password2=None):
        return self.client.post(reverse("accounts:register"), {
            "username": username,
            "email": "new@example.org",
            "password": self.password,
            "password2": self.password if password2 is None else password2,
        })

    def assert_logged_in(self, user):
        self.assertEqual(self.client.session[SESSION_KEY], str(user.pk))
        self.assertEqual(
            self.client.session[BACKEND_SESSION_KEY],
            "django.contrib.auth.backends.ModelBackend",
        )

    def test_login_variants_use_same_existing_account_and_preserve_casing(self):
        password_hash = self.user.password
        for username in self.variants:
            with self.subTest(username=username):
                self.client.logout()
                response = self.login(username)
                self.assertRedirects(response, reverse("dashboard:home"))
                self.assert_logged_in(self.user)
                self.user.refresh_from_db()
                self.assertEqual(self.user.username, "Funcy92")
                self.assertEqual(self.user.password, password_hash)
                self.assertEqual(User.objects.count(), 1)

    def test_wrong_password_and_password_case_changes_are_rejected(self):
        for username in self.variants:
            for password in ("incorrect", self.password.lower(), self.password.upper()):
                with self.subTest(username=username, password=password):
                    response = self.login(username, password)
                    self.assertContains(response, "Username or password is incorrect")
                    self.assertNotIn(SESSION_KEY, self.client.session)

    def test_password_whitespace_is_preserved(self):
        self.user.set_password(" " + self.password + " ")
        self.user.save()
        self.assertContains(self.login("FUNCY92"), "Username or password is incorrect")
        self.assertEqual(self.login("FUNCY92", " " + self.password + " ").status_code, 302)
        self.assert_logged_in(self.user)

    def test_unknown_user_is_rejected(self):
        self.assertContains(self.login("Missing"), "Username or password is incorrect")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_inactive_account_cannot_log_in_with_any_casing(self):
        self.user.is_active = False
        self.user.save()
        for username in self.variants:
            with self.subTest(username=username):
                self.assertContains(self.login(username), "Username or password is incorrect")
                self.assertNotIn(SESSION_KEY, self.client.session)

    def test_unusable_password_is_rejected(self):
        self.user.set_unusable_password()
        self.user.save()
        self.assertContains(self.login("FUNCY92"), "Username or password is incorrect")
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_legacy_case_collisions_fail_safely_without_changing_accounts(self):
        # Simulate a pre-migration database: the new index prevents new duplicates.
        for username in self.variants:
            with self.subTest(username=username):
                with patch.object(User.objects, "get", side_effect=User.MultipleObjectsReturned):
                    self.assertContains(self.login(username), "Username or password is incorrect")
                    self.assertNotIn(SESSION_KEY, self.client.session)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "Funcy92")

    def test_database_rejects_case_collisions_without_form_validation(self):
        for username in self.variants:
            with self.subTest(username=username):
                with self.assertRaises(IntegrityError), transaction.atomic():
                    User.objects.create_user(username, password=self.password)
        self.assertEqual(User.objects.count(), 1)

    def test_registration_handles_name_claimed_after_initial_check(self):
        original_filter = User.objects.filter
        lookups = []

        def simulate_stale_check(*args, **kwargs):
            if "username__iexact" in kwargs:
                lookups.append(kwargs)
                if len(lookups) == 1:
                    return User.objects.none()
            return original_filter(*args, **kwargs)

        with patch.object(User.objects, "filter", side_effect=simulate_stale_check):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.register("FUNCY92")
        self.assertContains(response, "Username already exists")
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)

    def test_unrelated_database_error_is_not_reported_as_username_collision(self):
        with patch.object(User.objects, "create_user", side_effect=IntegrityError("unrelated")):
            with self.assertRaises(IntegrityError):
                self.register("NewMember")

    def test_existing_default_backend_session_remains_valid(self):
        self.client.force_login(self.user, backend="django.contrib.auth.backends.ModelBackend")
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 302)
        self.assert_logged_in(self.user)

    def test_registration_rejects_case_collisions_including_inactive_accounts(self):
        for active in (True, False):
            self.user.is_active = active
            self.user.save()
            for username in (*self.variants, " funcy92 ", "ＦＵＮＣＹ９２"):
                with self.subTest(active=active, username=username):
                    with self.captureOnCommitCallbacks(execute=True):
                        response = self.register(username)
                    self.assertContains(response, "Username already exists")
                    self.assertEqual(User.objects.count(), 1)
                    self.assertEqual(len(mail.outbox), 0)

    def test_register_form_rejects_case_collisions(self):
        for username in (*self.variants, "ＦＵＮＣＹ９２"):
            with self.subTest(username=username):
                form = RegisterForm(data={
                    "username": username, "email": "new@example.org",
                    "password1": self.password, "password2": self.password,
                })
                self.assertFalse(form.is_valid())
                self.assertIn("username", form.errors)

    def test_register_form_preserves_new_username_casing(self):
        form = RegisterForm(data={
            "username": "NewMember", "email": "new@example.org",
            "password1": self.password, "password2": self.password,
        })
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.username, "NewMember")
        self.assertTrue(user.check_password(self.password))

    def test_registration_still_requires_matching_password_case(self):
        self.assertContains(self.register("NewMember", self.password.lower()), "Passwords do not match")
        self.assertEqual(User.objects.count(), 1)

    def test_verification_resend_activation_and_subsequent_login(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.assertContains(self.register("NewMember"), "Check Your Email")
        user = User.objects.get(username="NewMember")
        self.assertFalse(user.is_active)
        self.assertContains(self.login("NEWMEMBER"), "Username or password is incorrect")
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("accounts:resend_activation"), {"email": "NEW@example.org"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 2)
        link = re.search(r"https://accounts.example.org/\S+", mail.outbox[-1].body).group()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.get(link).status_code, 200)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(user.username, "NewMember")
        self.assert_logged_in(user)
        self.assertEqual(len(mail.outbox), 3)
        self.client.logout()
        self.assertEqual(self.login("NEWMEMBER").status_code, 302)
        self.assert_logged_in(user)
        with self.captureOnCommitCallbacks(execute=True):
            self.assertTemplateUsed(self.client.get(link), "accounts/activation_already_active.html")
        self.assertEqual(len(mail.outbox), 3)

    def test_password_reset_allows_mixed_case_login_with_only_new_password(self):
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("accounts:password_reset"), {"email": self.user.email})
        link = re.search(r"https://accounts.example.org/\S+", mail.outbox[-1].body).group()
        form_url = self.client.get(link).url
        password = "New-Reset-Password-789!"
        response = self.client.post(form_url, {"new_password1": password, "new_password2": password})
        self.assertRedirects(response, reverse("accounts:password_reset_complete"))
        self.assertContains(self.login("FUNCY92"), "Username or password is incorrect")
        self.assertContains(self.login("FUNCY92", password.lower()), "Username or password is incorrect")
        self.assertEqual(self.login("funcy92", password).status_code, 302)
        self.assert_logged_in(self.user)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "Funcy92")
