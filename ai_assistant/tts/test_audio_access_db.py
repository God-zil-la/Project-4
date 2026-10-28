from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from .audio_access import authorize_audio_request
from .errors import AuthorizationDenied
from .models import TTSAccount, TTSRequest


class AudioAccessDatabaseTests(TransactionTestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username="audio_owner")
        self.other = users.objects.create_user(username="audio_other")
        self.account = TTSAccount.objects.create(user=self.owner)
        self.key = uuid4()
        self.row = TTSRequest.objects.create(
            account=self.account,
            assistant_id=5,
            request_id=self.key,
            fingerprint="a" * 64,
        )

    def test_owner_can_access_own_request(self):
        with patch("ai_assistant.tts.audio_access.authorize",
                   return_value=self.owner.pk):
            result = authorize_audio_request(
                user=self.owner, assistant_id=5, request_id=self.key
            )
        self.assertEqual(result.pk, self.row.pk)

    def test_other_user_cannot_access_request(self):
        with patch("ai_assistant.tts.audio_access.authorize",
                   return_value=self.other.pk):
            with self.assertRaises(AuthorizationDenied):
                authorize_audio_request(
                    user=self.other, assistant_id=5, request_id=self.key
                )

    def test_wrong_assistant_cannot_access_request(self):
        with patch("ai_assistant.tts.audio_access.authorize",
                   return_value=self.owner.pk):
            with self.assertRaises(AuthorizationDenied):
                authorize_audio_request(
                    user=self.owner, assistant_id=6, request_id=self.key
                )
