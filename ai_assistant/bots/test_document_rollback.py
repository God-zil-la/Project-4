from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from .document_pipeline import create_chat_document


class DocumentRollbackTests(SimpleTestCase):

    @patch.dict("os.environ", {"R2_BUCKET_NAME": "test-bucket"})
    @patch("ai_assistant.bots.document_storage._client")
    @patch(
        "ai_assistant.bots.document_models."
        "GeneratedDocument.objects.create"
    )
    @patch("ai_assistant.bots.document_pipeline.upload_document")
    def test_database_failure_deletes_uploaded_r2_file(
        self, mock_upload, mock_create, mock_client
    ):
        user = Mock()
        user.pk = 101
        user.is_authenticated = True

        bot = Mock()
        bot.pk = 202
        bot.owner_id = 101

        conversation = Mock()
        conversation.user_id = 101
        conversation.bot_id = 202

        file_id = ("a" * 32) + ".pdf"

        mock_upload.return_value = {
            "file_id": file_id,
            "size_bytes": 1200,
        }

        mock_create.side_effect = RuntimeError(
            "Simulated database failure"
        )

        with self.assertRaisesRegex(
            RuntimeError, "Simulated database failure"
        ):
            create_chat_document(
                user=user,
                bot=bot,
                conversation=conversation,
                title="Workbook",
                content="Chapter 1 and exercises",
                file_format="pdf",
            )

        mock_client.return_value.delete_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="generated-documents/" + file_id,
        )

    @patch("ai_assistant.bots.document_pipeline.upload_document")
    def test_invalid_owner_still_prevents_upload(self, mock_upload):
        user = Mock(pk=101, is_authenticated=True)
        bot = Mock(pk=202, owner_id=999)
        conversation = Mock(user_id=101, bot_id=202)

        with self.assertRaises(PermissionError):
            create_chat_document(
                user=user,
                bot=bot,
                conversation=conversation,
                title="Workbook",
                content="Chapter 1",
                file_format="pdf",
            )

        mock_upload.assert_not_called()
