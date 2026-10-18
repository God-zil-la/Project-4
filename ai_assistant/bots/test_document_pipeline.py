from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from django.urls import resolve

from .document_pipeline import create_chat_document


class DocumentPipelineTests(SimpleTestCase):

    def setUp(self):
        self.user = Mock()
        self.user.pk = 123
        self.user.is_authenticated = True

    @override_settings(SECRET_KEY="test-document-secret")
    @patch("ai_assistant.bots.document_pipeline.upload_document")
    def test_all_formats_generate_secure_downloads(self, mock_upload):
        for extension in ("pdf", "docx", "xlsx", "csv"):
            with self.subTest(extension=extension):
                file_id = ("a" * 32) + "." + extension

                mock_upload.return_value = {
                    "file_id": file_id,
                    "size_bytes": 500,
                    "download_url": "https://example.invalid/private",
                }

                result = create_chat_document(
                    user=self.user,
                    title="My Workbook",
                    content={
                        "xlsx": '{"sheets":[{"name":"Data","rows":[["Item","Value"],["A",1]]}]}',
                        "csv": "Item,Value,Note\nA,1,Example",
                    }.get(extension, "Chapter 1\nExercise 1"),
                    file_format=extension,
                )

                uploaded_bytes = mock_upload.call_args.args[0]

                self.assertGreater(len(uploaded_bytes), 0)
                self.assertEqual(result["format"], extension)
                self.assertEqual(result["file_id"], file_id)
                self.assertEqual(result["size_bytes"], 500)

                self.assertNotIn(
                    "example.invalid",
                    result["download_url"],
                )

                matched = resolve(result["download_url"])
                self.assertEqual(
                    matched.url_name,
                    "document-download",
                )

    @patch("ai_assistant.bots.document_pipeline.upload_document")
    def test_unauthenticated_user_cannot_generate(self, mock_upload):
        user = Mock()
        user.is_authenticated = False

        with self.assertRaises(PermissionError):
            create_chat_document(
                user=user,
                title="Test",
                content="Content",
                file_format="pdf",
            )

        mock_upload.assert_not_called()

    @patch("ai_assistant.bots.document_pipeline.upload_document")
    def test_empty_document_not_uploaded(self, mock_upload):
        with self.assertRaises(ValueError):
            create_chat_document(
                user=self.user,
                title="Test",
                content=" ",
                file_format="pdf",
            )

        mock_upload.assert_not_called()

    @patch("ai_assistant.bots.document_pipeline.upload_document")
    def test_unsupported_format_not_uploaded(self, mock_upload):
        with self.assertRaises(ValueError):
            create_chat_document(
                user=self.user,
                title="Test",
                content="Content",
                file_format="exe",
            )

        mock_upload.assert_not_called()
