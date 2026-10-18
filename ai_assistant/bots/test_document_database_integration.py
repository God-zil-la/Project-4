import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import Bot, Conversation
from .document_models import GeneratedDocument
from .document_pipeline import create_chat_document


class DocumentDatabaseIntegrationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.owner = User.objects.create_user(
            username="doc_owner_test",
            password="LocalTestOnly123!",
        )
        cls.other = User.objects.create_user(
            username="doc_other_test",
            password="LocalTestOnly123!",
        )

        category_field = Bot._meta.get_field("category")
        choices = [
            value for value, label in category_field.flatchoices
            if value not in ("", None)
        ]

        bot_kwargs = {
            "owner": cls.owner,
            "name": "Document Test Assistant",
        }

        if choices:
            bot_kwargs["category"] = choices[0]

        cls.bot = Bot.objects.create(**bot_kwargs)

        cls.conversation = Conversation.objects.create(
            user=cls.owner,
            bot=cls.bot,
        )

    @patch("ai_assistant.bots.document_pipeline.upload_document")
    def test_document_persists_with_correct_ownership(self, upload):
        file_id = uuid.uuid4().hex + ".pdf"

        upload.return_value = {
            "file_id": file_id,
            "size_bytes": 1200,
        }

        result = create_chat_document(
            user=self.owner,
            bot=self.bot,
            conversation=self.conversation,
            title="My Workbook",
            content="Chapter 1\nIntroduction\nExercises",
            file_format="pdf",
        )

        document = GeneratedDocument.objects.get(
            pk=result["document_id"]
        )

        self.assertEqual(document.owner_id, self.owner.pk)
        self.assertEqual(document.bot_id, self.bot.pk)
        self.assertEqual(
            document.conversation_id,
            self.conversation.pk,
        )
        self.assertEqual(document.file_format, "pdf")
        self.assertEqual(
            document.object_key,
            "generated-documents/" + file_id,
        )
        self.assertEqual(
            result["download_url"],
            reverse(
                "bots:saved-document-download",
                kwargs={"document_id": document.pk},
            ),
        )

    @patch("ai_assistant.bots.document_mobile_api._client")
    @patch.dict("os.environ", {"R2_BUCKET_NAME": "test-bucket"})
    def test_owner_can_request_link_but_other_cannot(self, client):
        document = GeneratedDocument.objects.create(
            owner=self.owner,
            bot=self.bot,
            conversation=self.conversation,
            object_key="generated-documents/" + uuid.uuid4().hex + ".pdf",
            filename="document.pdf",
            file_format="pdf",
            size_bytes=1200,
        )

        client.return_value.generate_presigned_url.return_value = (
            "https://example.invalid/short-lived"
        )

        url = reverse(
            "bots:mobile-document-link",
            kwargs={"document_id": document.pk},
        )

        api = APIClient()
        api.force_authenticate(user=self.owner)
        response = api.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["download_url"],
            "https://example.invalid/short-lived",
        )

        client.reset_mock()
        api.force_authenticate(user=self.other)
        response = api.get(url)

        self.assertEqual(response.status_code, 404)
        client.assert_not_called()

    def test_document_list_respects_ownership(self):
        GeneratedDocument.objects.create(
            owner=self.owner,
            bot=self.bot,
            conversation=self.conversation,
            object_key="generated-documents/" + uuid.uuid4().hex + ".docx",
            filename="document.docx",
            file_format="docx",
            size_bytes=2345,
        )

        url = reverse(
            "bots:conversation-documents",
            kwargs={
                "conversation_id": self.conversation.public_id
            },
        )

        api = APIClient()
        api.force_authenticate(user=self.owner)
        response = api.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["documents"]), 1)
        self.assertEqual(
            response.data["documents"][0]["format"],
            "docx",
        )

        api.force_authenticate(user=self.other)
        response = api.get(url)

        self.assertEqual(response.status_code, 404)

    def test_web_history_contains_saved_document(self):
        document = GeneratedDocument.objects.create(
            owner=self.owner,
            bot=self.bot,
            conversation=self.conversation,
            object_key="generated-documents/" + uuid.uuid4().hex + ".xlsx",
            filename="document.xlsx",
            file_format="xlsx",
            size_bytes=3500,
        )

        self.client.force_login(self.owner)

        response = self.client.get(
            reverse(
                "bots:bot_chat_api",
                kwargs={"bot_id": self.bot.pk},
            ),
            {"conversation_id": str(self.conversation.public_id)},
        )

        self.assertEqual(response.status_code, 200)
        documents = response.json()["documents"]
        self.assertEqual(len(documents), 1)
        self.assertEqual(
            documents[0]["document_id"],
            str(document.pk),
        )
