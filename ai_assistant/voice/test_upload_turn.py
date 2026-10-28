"""U6.3 upload-to-turn integration tests."""

import uuid

from django.test import TestCase

from .models import VoiceTurn
from .test_upload_api import VoiceUploadAPITests, sample_wav


class VoiceUploadTurnTests(TestCase):
    setUp = VoiceUploadAPITests.setUp
    upload = VoiceUploadAPITests.upload

    def test_upload_creates_voice_turn(self):
        self.client.force_login(self.owner)
        request_id = str(uuid.uuid4())

        response = self.client.post(
            self.url,
            {
                "audio": self.upload(sample_wav()),
                "request_id": request_id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "created")
        self.assertEqual(response.json()["request_id"], request_id)
        self.assertTrue(response.json()["created"])
        self.assertEqual(VoiceTurn.objects.count(), 1)

    def test_upload_replay_is_idempotent(self):
        self.client.force_login(self.owner)
        request_id = str(uuid.uuid4())

        first = self.client.post(
            self.url,
            {
                "audio": self.upload(sample_wav()),
                "request_id": request_id,
            },
        )

        second = self.client.post(
            self.url,
            {
                "audio": self.upload(sample_wav()),
                "request_id": request_id,
            },
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertFalse(second.json()["created"])
        self.assertEqual(VoiceTurn.objects.count(), 1)

    def test_invalid_request_id_creates_no_turn(self):
        self.client.force_login(self.owner)

        response = self.client.post(
            self.url,
            {
                "audio": self.upload(sample_wav()),
                "request_id": "not-a-uuid",
            },
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(VoiceTurn.objects.count(), 0)
