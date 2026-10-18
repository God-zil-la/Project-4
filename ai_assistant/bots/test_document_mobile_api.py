import uuid
from unittest.mock import Mock, patch

from django.http import Http404
from django.test import SimpleTestCase
from django.urls import reverse, resolve

from rest_framework.test import APIRequestFactory, force_authenticate


class MobileDocumentLinkTests(SimpleTestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.document_id = uuid.uuid4()
        self.user = Mock()
        self.user.pk = 101
        self.user.is_authenticated = True

    def request_link(self, user):
        path = reverse(
            "bots:mobile-document-link",
            kwargs={"document_id": self.document_id},
        )
        request = self.factory.get(path)
        if user is not None:
            force_authenticate(request, user=user)
        match = resolve(path)
        return match.func(request, **match.kwargs)

    @patch.dict("os.environ", {"R2_BUCKET_NAME": "test-bucket"})
    @patch("ai_assistant.bots.document_mobile_api._client")
    @patch("ai_assistant.bots.document_mobile_api.get_object_or_404")
    def test_owner_gets_temporary_link(self, mock_get, mock_client):
        document = Mock()
        document.pk = self.document_id
        document.object_key = "generated-documents/" + "a" * 32 + ".pdf"
        document.filename = "document.pdf"
        document.file_format = "pdf"
        mock_get.return_value = document

        mock_client.return_value.generate_presigned_url.return_value = (
            "https://example.invalid/temporary-file"
        )

        response = self.request_link(self.user)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["expires_in"], 60)
        self.assertEqual(response.data["format"], "pdf")
        self.assertEqual(response["Cache-Control"], "no-store")

        filters = mock_get.call_args.kwargs
        self.assertEqual(filters["owner"], self.user)
        self.assertEqual(filters["bot__owner"], self.user)
        self.assertEqual(filters["conversation__user"], self.user)
        mock_client.return_value.generate_presigned_url.assert_called_once()

    @patch("ai_assistant.bots.document_mobile_api._client")
    @patch("ai_assistant.bots.document_mobile_api.get_object_or_404")
    def test_anonymous_user_denied(self, mock_get, mock_client):
        response = self.request_link(None)
        self.assertIn(response.status_code, (401, 403))
        mock_get.assert_not_called()
        mock_client.assert_not_called()

    @patch("ai_assistant.bots.document_mobile_api._client")
    @patch("ai_assistant.bots.document_mobile_api.get_object_or_404")
    def test_missing_or_unowned_document_denied(
        self, mock_get, mock_client
    ):
        mock_get.side_effect = Http404("Document not found")
        response = self.request_link(self.user)

        self.assertEqual(response.status_code, 404)
        mock_client.assert_not_called()
