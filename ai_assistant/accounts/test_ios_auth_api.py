"""Regression coverage for the native/mobile authentication API."""

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token


@override_settings(PUBLIC_BASE_URL="https://accounts.example.org")
class IOSAuthAPITests(TestCase):
    password = "Strong-Test-Password-194!"
    variants = ("Funcy92", "funcy92", "FUNCY92", "FuNcY92")

    def setUp(self):
        self.user = User.objects.create_user(
            username="Funcy92",
            email="member@example.org",
            password=self.password,
        )

    def login(self, username, password=None):
        return self.client.post(
            reverse("accounts:ios-login-api"),
            {
                "username": username,
                "password": self.password if password is None else password,
            },
            content_type="application/json",
        )

    def register(self, **overrides):
        data = {
            "username": "NewUser92",
            "email": "newuser@example.org",
            "password": self.password,
            "password2": self.password,
        }
        data.update(overrides)

        return self.client.post(
            reverse("accounts:ios-register-api"),
            data,
            content_type="application/json",
        )

    def test_username_variants_authenticate_same_existing_user(self):
        for username in self.variants:
            with self.subTest(username=username):
                response = self.login(username)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["username"], "Funcy92")

                self.user.refresh_from_db()

                self.assertEqual(self.user.username, "Funcy92")
                self.assertEqual(User.objects.count(), 1)

    def test_successful_login_reuses_same_token(self):
        first_response = self.login("Funcy92")
        second_response = self.login("funcy92")

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        self.assertEqual(
            first_response.json()["token"],
            second_response.json()["token"],
        )
        self.assertEqual(
            Token.objects.filter(user=self.user).count(),
            1,
        )

    def test_wrong_password_is_rejected(self):
        response = self.login("FUNCY92", "incorrect")

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("token", response.json())

    def test_inactive_user_is_rejected(self):
        self.user.is_active = False
        self.user.save()

        response = self.login("funcy92")

        self.assertEqual(response.status_code, 400)
        self.assertNotIn("token", response.json())

    def test_registration_creates_inactive_user(self):
        response = self.register()

        self.assertEqual(response.status_code, 201)

        user = User.objects.get(username="NewUser92")

        self.assertEqual(user.email, "newuser@example.org")
        self.assertFalse(user.is_active)
        self.assertTrue(user.check_password(self.password))
        self.assertTrue(hasattr(user, "profile"))

    def test_registration_rejects_case_insensitive_duplicate_username(self):
        response = self.register(username="fUnCy92")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_registration_rejects_duplicate_email_case_insensitively(self):
        response = self.register(email="MEMBER@EXAMPLE.ORG")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_registration_rejects_mismatched_passwords(self):
        response = self.register(
            password2="Different-Password-194!"
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_registration_rejects_invalid_email(self):
        response = self.register(email="not-an-email")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_registration_sends_verification_email(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.register()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(mail.outbox), 1)

        message = mail.outbox[0]

        self.assertEqual(
            message.subject,
            "Verify your email - AI Assistant",
        )
        self.assertEqual(
            message.to,
            ["newuser@example.org"],
        )
        self.assertIn(
            "https://accounts.example.org/accounts/activate/",
            message.body,
        )

    def test_registration_rejects_weak_password(self):
        response = self.register(
            password="password",
            password2="password",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(User.objects.count(), 1)

    def test_me_returns_authenticated_user(self):
        token = Token.objects.create(user=self.user)

        response = self.client.get(
            reverse("accounts:ios-me-api"),
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "username": "Funcy92",
            },
        )

    def test_me_rejects_missing_token(self):
        response = self.client.get(
            reverse("accounts:ios-me-api"),
        )

        self.assertEqual(response.status_code, 401)

    def test_me_rejects_invalid_token(self):
        response = self.client.get(
            reverse("accounts:ios-me-api"),
            HTTP_AUTHORIZATION="Token invalid-token",
        )

        self.assertEqual(response.status_code, 401)