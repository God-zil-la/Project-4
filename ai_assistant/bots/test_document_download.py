from django.test import SimpleTestCase, override_settings
from django.urls import resolve, reverse
from django.core import signing

from rest_framework.test import (
    APIRequestFactory,
    force_authenticate,
)

from unittest.mock import Mock, patch

from .document_download import (
    create_document_download,
    TOKEN_SALT,
    TOKEN_MAX_AGE,
)


class DocumentDownloadSecurityTests(SimpleTestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.owner = Mock()
        self.owner.pk = 101
        self.owner.is_authenticated = True

        self.other = Mock()
        self.other.pk = 202
        self.other.is_authenticated = True

        self.file_id = ("a" * 32) + ".pdf"

    def request_download(self, path, user):
        request = self.factory.get(path)
        if user is not None:
            force_authenticate(request, user=user)
        return resolve(path).func(
            request,
            **resolve(path).kwargs,
        )

    @override_settings(SECRET_KEY="document-test-secret")
    @patch("ai_assistant.bots.document_download._client")
    @patch.dict("os.environ", {"R2_BUCKET_NAME": "test-bucket"})
    def test_owner_can_download(self, mock_client):
        mock_client.return_value.generate_presigned_url.return_value = (
            "https://example.invalid/signed-download"
        )

        path = create_document_download(self.owner, self.file_id)
        response = self.request_download(path, self.owner)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            "https://example.invalid/signed-download",
        )
        self.assertEqual(response["Cache-Control"], "no-store")

        mock_client.return_value.generate_presigned_url.assert_called_once()

    @override_settings(SECRET_KEY="document-test-secret")
    @patch("ai_assistant.bots.document_download._client")
    def test_other_user_cannot_download(self, mock_client):
        path = create_document_download(self.owner, self.file_id)
        response = self.request_download(path, self.other)

        self.assertEqual(response.status_code, 404)
        mock_client.assert_not_called()

    @override_settings(SECRET_KEY="document-test-secret")
    @patch("ai_assistant.bots.document_download._client")
    def test_unauthenticated_request_is_rejected(self, mock_client):
        path = create_document_download(self.owner, self.file_id)
        response = self.request_download(path, None)

        self.assertIn(response.status_code, (401, 403))
        mock_client.assert_not_called()

    @override_settings(SECRET_KEY="document-test-secret")
    @patch("ai_assistant.bots.document_download._client")
    def test_invalid_signature_is_rejected(self, mock_client):
        path = create_document_download(self.owner, self.file_id)
        token = path.rstrip("/").split("/")[-2]
        altered = token[:-1] + ("X" if token[-1] != "X" else "Y")
        bad_path = path.replace(token, altered)

        response = self.request_download(bad_path, self.owner)
        self.assertEqual(response.status_code, 404)
        mock_client.assert_not_called()

    @override_settings(SECRET_KEY="document-test-secret")
    def test_invalid_file_id_is_rejected(self):
        with self.assertRaises(ValueError):
            create_document_download(self.owner, "../secret.pdf")
