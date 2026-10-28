"""Authentication and request-validation tests for the isolated TTS API."""
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from .api_views import SavedResponseTTSAPIView
from .service import Result


class SavedResponseAPITests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = SavedResponseTTSAPIView.as_view()
        self.user = get_user_model().objects.create_user(
            username="tts-api-test-user"
        )
        self.payload = {
            "assistant_id": 7,
            "conversation_id": str(uuid4()),
            "message_id": 42,
            "request_id": str(uuid4()),
        }

    def test_anonymous_request_denied(self):
        request = self.factory.post("/tts/", self.payload, format="json")
        with patch(
            "ai_assistant.tts.api_views.synthesize_saved_response"
        ) as synthesize:
            response = self.view(request)
        self.assertIn(response.status_code, (401, 403))
        synthesize.assert_not_called()

    def test_invalid_payload_rejected(self):
        request = self.factory.post(
            "/tts/", {"assistant_id": 7}, format="json"
        )
        force_authenticate(request, user=self.user)
        with patch(
            "ai_assistant.tts.api_views.synthesize_saved_response"
        ) as synthesize:
            response = self.view(request)
        self.assertEqual(response.status_code, 400)
        synthesize.assert_not_called()

    def test_authenticated_request_returns_status_without_mock_audio(self):
        request = self.factory.post("/tts/", self.payload, format="json")
        force_authenticate(request, user=self.user)
        with patch(
            "ai_assistant.tts.api_views.synthesize_saved_response",
            return_value=Result(uuid4(), "succeeded", b"MOCK-AUDIO"),
        ) as synthesize:
            response = self.view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["state"], "succeeded")
        self.assertFalse(response.data["audio_available"])
        self.assertNotIn("audio", response.data)
        synthesize.assert_called_once()
    def test_real_token_authentication(self):
        from rest_framework.authtoken.models import Token

        token = Token.objects.create(user=self.user)
        request = self.factory.post(
            "/tts/", self.payload, format="json",
            HTTP_AUTHORIZATION=f"Token {token.key}",
        )

        with patch(
            "ai_assistant.tts.api_views.synthesize_saved_response",
            return_value=Result(uuid4(), "succeeded"),
        ) as synthesize:
            response = self.view(request)

        self.assertEqual(response.status_code, 200)
        synthesize.assert_called_once()

    def test_invalid_token_rejected(self):
        request = self.factory.post(
            "/tts/", self.payload, format="json",
            HTTP_AUTHORIZATION="Token invalid-token",
        )

        with patch(
            "ai_assistant.tts.api_views.synthesize_saved_response"
        ) as synthesize:
            response = self.view(request)

        self.assertEqual(response.status_code, 401)
        synthesize.assert_not_called()

    def test_session_authentication_requires_csrf(self):
        from rest_framework.test import APIRequestFactory

        factory = APIRequestFactory(enforce_csrf_checks=True)
        request = factory.post("/tts/", self.payload, format="json")
        force_authenticate(request, user=self.user)

        # force_authenticate bypasses normal session authentication,
        # so use an actual authenticated Django session instead.
        request._force_auth_user = None
        request._force_auth_token = None
        request.user = self.user

        with patch(
            "ai_assistant.tts.api_views.synthesize_saved_response"
        ) as synthesize:
            response = self.view(request)

        self.assertEqual(response.status_code, 403)
        synthesize.assert_not_called()

    @override_settings(ROOT_URLCONF='ai_assistant.tts.test_urls')
    def test_valid_session_with_csrf_is_accepted(self):
        from rest_framework.test import APIClient

        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        csrf_token = "a" * 32
        client.cookies["csrftoken"] = csrf_token

        with patch(
            "ai_assistant.tts.api_views.synthesize_saved_response",
            return_value=Result(uuid4(), "succeeded"),
        ) as synthesize:
            response = client.post(
                "/tts/",
                self.payload,
                format="json",
                HTTP_X_CSRFTOKEN=csrf_token,
            )

        self.assertEqual(response.status_code, 200)
        synthesize.assert_called_once()
