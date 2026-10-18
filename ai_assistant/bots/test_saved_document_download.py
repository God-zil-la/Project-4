import uuid
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from django.urls import reverse, resolve

from rest_framework.test import (
    APIRequestFactory,
    force_authenticate,
)


class SavedDocumentDownloadTests(SimpleTestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = Mock()
        self.user.pk = 123
        self.user.is_authenticated = True
        self.document_id = uuid.uuid4()

    def get_response(self, user):
        path = reverse(
            "bots:saved-document-download",
            kwargs={"document_id": self.document_id},
        )
        request = self.factory.get(path)
        if user is not None:
            force_authenticate(request, user=user)

        match = resolve(path)
        return match.func(request, **match.kwargs)

    @override_settings(SECRET_KEY="test-secret")
    @patch.dict("os.environ", {"R2_BUCKET_NAME": "test-bucket"})
    @patch("ai_assistant.bots.saved_document_download._client")
    @patch(
        "ai_assistant.bots.saved_document_download.get_object_or_404"
    )
    def test_owner_receives_new_signed_url(self, mock_get, mock_client):
        document = Mock()
        document.object_key = (
            "generated-documents/"
            + ("a" * 32)
            + ".pdf"
        )
        document.filename = "workbook.pdf"
        mock_get.return_value = document

        mock_client.return_value.generate_presigned_url.return_value = (
            "https://example.invalid/short-lived"
        )

        response = self.get_response(self.user)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "https://example.invalid/short-lived",
        )

        self.assertEqual(response["Cache-Control"], "no-store")

        filters = mock_get.call_args.kwargs
        self.assertEqual(filters["owner"], self.user)
        self.assertEqual(filters["bot__owner"], self.user)
        self.assertEqual(filters["conversation__user"], self.user)

        mock_client.return_value.generate_presigned_url.assert_called_once()

    @patch(
        "ai_assistant.bots.saved_document_download.get_object_or_404"
    )
    @patch("ai_assistant.bots.saved_document_download._client")
    def test_unauthenticated_user_denied(self, mock_client, mock_get):
        response = self.get_response(None)
        self.assertIn(response.status_code, (401, 403))
        mock_get.assert_not_called()
        mock_client.assert_not_called()
