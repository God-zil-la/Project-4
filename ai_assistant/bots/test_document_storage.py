from unittest.mock import Mock, patch
from botocore.exceptions import ClientError
from django.test import SimpleTestCase

from .document_storage import (
    upload_document,
    MAX_DOCUMENT_BYTES,
    FORMATS,
)


class DocumentStorageTests(SimpleTestCase):

    @patch.dict("os.environ", {"R2_BUCKET_NAME": "private-test-bucket"})
    @patch("ai_assistant.bots.document_storage._client")
    def test_every_format_uploads_privately(self, mock_client):
        client = Mock()
        client.generate_presigned_url.return_value = (
            "https://example.invalid/temporary"
        )
        mock_client.return_value = client

        for extension in ("pdf", "docx", "xlsx", "csv"):
            with self.subTest(extension=extension):
                client.reset_mock()

                data = b"document test content"
                result = upload_document(data, extension)

                self.assertEqual(result["format"], extension)
                self.assertEqual(result["size_bytes"], len(data))
                self.assertTrue(result["file_id"].endswith("." + extension))
                self.assertEqual(result["expires_in"], 900)

                args = client.put_object.call_args.kwargs

                self.assertEqual(
                    args["Bucket"],
                    "private-test-bucket",
                )
                self.assertEqual(args["Body"], data)
                self.assertEqual(
                    args["ContentType"],
                    FORMATS[extension][0],
                )
                self.assertTrue(
                    args["Key"].startswith("generated-documents/")
                )
                self.assertNotIn("ACL", args)

                client.generate_presigned_url.assert_called_once()

    @patch("ai_assistant.bots.document_storage._client")
    def test_invalid_format_never_uploads(self, mock_client):
        with self.assertRaises(ValueError):
            upload_document(b"content", "exe")
        mock_client.assert_not_called()

    @patch("ai_assistant.bots.document_storage._client")
    def test_empty_data_never_uploads(self, mock_client):
        with self.assertRaises(ValueError):
            upload_document(b"", "pdf")
        mock_client.assert_not_called()

    @patch("ai_assistant.bots.document_storage._client")
    def test_oversized_data_never_uploads(self, mock_client):
        with self.assertRaises(ValueError):
            upload_document(
                b"x" * (MAX_DOCUMENT_BYTES + 1),
                "pdf",
            )
        mock_client.assert_not_called()

    @patch.dict("os.environ", {"R2_BUCKET_NAME": "private-test-bucket"})
    @patch("ai_assistant.bots.document_storage._client")
    def test_upload_failure_never_returns_download(self, mock_client):
        mock_client.return_value.put_object.side_effect = ClientError(
            {
                "Error": {
                    "Code": "AccessDenied",
                    "Message": "Upload denied",
                }
            },
            "PutObject",
        )

        with self.assertRaises(ClientError):
            upload_document(b"content", "pdf")

        mock_client.return_value.generate_presigned_url.assert_not_called()
