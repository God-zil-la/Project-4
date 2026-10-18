import uuid
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from pypdf import PdfReader

from .models import Bot, Conversation
from .document_models import GeneratedDocument
from .document_intent import (
    requested_document_format,
    document_content_ready,
)
from .document_pipeline import create_chat_document


class DocumentCompleteFlowTests(TestCase):

    def setUp(self):
        User = get_user_model()
        suffix = uuid.uuid4().hex[:8]

        self.owner = User.objects.create_user(
            username="document_flow_" + suffix,
            password="LocalTest123!",
        )

        self.other = User.objects.create_user(
            username="other_flow_" + suffix,
            password="LocalTest123!",
        )

        choices = [
            value
            for value, _ in Bot._meta.get_field(
                "category"
            ).flatchoices
            if value not in ("", None)
        ]

        kwargs = {
            "owner": self.owner,
            "name": "Workbook Assistant",
        }

        if choices:
            kwargs["category"] = choices[0]

        self.bot = Bot.objects.create(**kwargs)

        self.conversation = Conversation.objects.create(
            user=self.owner,
            bot=self.bot,
        )

    @patch.dict(
        "os.environ",
        {"R2_BUCKET_NAME": "document-test-bucket"},
    )
    @patch("ai_assistant.bots.document_mobile_api._client")
    @patch("ai_assistant.bots.document_storage._client")
    def test_request_to_file_and_secure_download(
        self,
        storage_client,
        mobile_client,
    ):
        request_text = (
            "Kan du göra en arbetsbok till mig och "
            "göra ett nedladdningsbart dokument?"
        )

        file_format = requested_document_format(
            request_text
        )

        self.assertEqual(file_format, "docx")

        # Example of completed AI-authored workbook content.
        content = (
            "Business Workbook\n\n"
            "Chapter 1: Planning your business. "
            "Write down your primary business goals "
            "and describe your ideal customers.\n\n"
            "Chapter 2: Daily operations. "
            "Identify the activities that require "
            "your attention every working day.\n\n"
            "Exercise 1: Create a practical checklist "
            "covering communication, customer service, "
            "planning, budgeting, and follow-up.\n\n"
            "Exercise 2: Review your progress and "
            "identify three improvements for next week."
        )

        self.assertTrue(
            document_content_ready(
                request_text,
                content,
            )
        )

        result = create_chat_document(
            user=self.owner,
            bot=self.bot,
            conversation=self.conversation,
            title="Business Workbook",
            content=content,
            file_format=file_format,
        )

        self.assertEqual(result["format"], "docx")

        document = GeneratedDocument.objects.get(
            pk=result["document_id"]
        )

        self.assertEqual(
            document.owner_id,
            self.owner.pk,
        )
        self.assertEqual(
            document.conversation_id,
            self.conversation.pk,
        )

        upload = storage_client.return_value.put_object
        upload.assert_called_once()

        uploaded_bytes = upload.call_args.kwargs["Body"]

        from docx import Document

        generated = Document(BytesIO(uploaded_bytes))

        combined_text = "\n".join(
            paragraph.text
            for paragraph in generated.paragraphs
        )

        self.assertIn("Business Workbook", combined_text)
        self.assertIn("Exercise 2", combined_text)

        signed_url = (
            "https://example.invalid/temporary-download"
        )

        mobile_client.return_value.generate_presigned_url.return_value = (
            signed_url
        )

        endpoint = reverse(
            "bots:mobile-document-link",
            kwargs={"document_id": document.pk},
        )

        api = APIClient()
        api.force_authenticate(user=self.owner)

        response = api.get(endpoint)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["download_url"],
            signed_url,
        )

        api.force_authenticate(user=self.other)

        denied = api.get(endpoint)

        self.assertEqual(denied.status_code, 404)

        # A different user must not receive another R2 URL.
        self.assertEqual(
            mobile_client.return_value
            .generate_presigned_url.call_count,
            1,
        )

        print(
            "PASS: Request -> DOCX -> R2 upload -> "
            "database -> owner download -> denied other user"
        )
