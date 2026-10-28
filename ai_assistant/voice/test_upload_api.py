import io
import wave

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from ai_assistant.voice.service import start_session
from ai_assistant.bots.models import Bot, Conversation


def sample_wav():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(bytes(32000))
    return buffer.getvalue()


@override_settings(ALLOWED_HOSTS=["testserver"])
class VoiceUploadAPITests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="voice_upload_owner",
            password="unused-test-password",
        )
        self.other = User.objects.create_user(
            username="voice_upload_other",
            password="unused-test-password",
        )

        self.bot = Bot.objects.create(
            owner=self.owner,
            name="Voice test assistant",
        )
        self.conversation = Conversation.objects.create(
            user=self.owner,
            bot=self.bot,
        )
        self.session = start_session(
            user=self.owner,
            assistant=self.bot,
            conversation=self.conversation,
        )
        self.url = f"/api/live-voice/{self.session.public_id}/upload/"

    def upload(self, data):
        return SimpleUploadedFile(
            "voice.wav",
            data,
            content_type="audio/wav",
        )

    def test_valid_wav(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {"audio": self.upload(sample_wav())},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "validated")

    def test_invalid_wav(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {"audio": self.upload(b"not a wav")},
        )
        self.assertEqual(response.status_code, 400)

    def test_other_user_denied(self):
        self.client.force_login(self.other)
        response = self.client.post(
            self.url,
            {"audio": self.upload(sample_wav())},
        )
        self.assertIn(response.status_code, (403, 404))

    def test_closed_session_denied(self):
        self.session.active = False
        self.session.save(update_fields=["active"])
        self.client.force_login(self.owner)
        response = self.client.post(
            self.url,
            {"audio": self.upload(sample_wav())},
        )
        self.assertIn(response.status_code, (404, 409))

    def test_missing_audio(self):
        self.client.force_login(self.owner)
        response = self.client.post(self.url, {})
        self.assertEqual(response.status_code, 400)
