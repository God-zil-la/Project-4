from unittest.mock import Mock, patch
from django.test import SimpleTestCase
from django.urls import resolve

from .document_pipeline import create_chat_document


class DocumentPersistenceTests(SimpleTestCase):

    @patch(
        "ai_assistant.bots.document_models."
        "GeneratedDocument.objects.create",
        create=True,
    )
    @patch("ai_assistant.bots.document_pipeline.upload_document")
    def test_document_is_saved_with_owner_and_conversation(
        self, mock_upload, mock_create
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

        mock_upload.return_value = {
            "file_id": ("a" * 32) + ".pdf",
            "size_bytes": 1500,
        }

        import uuid
        document_id = uuid.uuid4()

        mock_create.return_value.pk = document_id

        result = create_chat_document(
            user=user,
            bot=bot,
            conversation=conversation,
            title="Workbook",
            content="Introduction and exercises",
            file_format="pdf",
        )

        self.assertEqual(
            result["document_id"], str(document_id)
        )

        self.assertEqual(
            resolve(result["download_url"]).url_name,
            "saved-document-download",
        )

        mock_create.assert_called_once()

        values = mock_create.call_args.kwargs

        self.assertIs(values["owner"], user)
        self.assertIs(values["bot"], bot)
        self.assertIs(values["conversation"], conversation)

    @patch("ai_assistant.bots.document_pipeline.upload_document")
    def test_invalid_ownership_is_blocked(self, mock_upload):
        user = Mock(pk=101, is_authenticated=True)
        bot = Mock(pk=202, owner_id=999)
        conversation = Mock(user_id=101, bot_id=202)

        # Invalid ownership must be rejected before any upload.
        mock_upload.return_value = {
            "file_id": ("b" * 32) + ".pdf",
            "size_bytes": 200,
        }

        with self.assertRaises(PermissionError):
            create_chat_document(
                user=user,
                bot=bot,
                conversation=conversation,
                title="Workbook",
                content="Workbook content",
                file_format="pdf",
            )

        mock_upload.assert_not_called()
