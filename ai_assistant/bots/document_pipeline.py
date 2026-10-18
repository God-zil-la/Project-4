from .document_generator import generate_document
from .document_storage import upload_document
from .document_download import create_document_download


SUPPORTED_FORMATS = frozenset(("pdf", "docx", "xlsx", "csv"))


def create_chat_document(*, user, title, content, file_format, conversation=None, bot=None):
    """
    Generate, upload and register a secure document download.

    Caller must already have authenticated the user and verified
    that the requested document belongs to their conversation.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        raise PermissionError("Authentication is required.")

    file_format = str(file_format).strip().lower()

    if file_format not in SUPPORTED_FORMATS:
        raise ValueError("Unsupported file format.")

    title = str(title).strip()
    content = str(content).strip()

    if not title:
        raise ValueError("Document title is required.")

    if not content:
        raise ValueError("Document content is required.")

    # Verify ownership BEFORE creating or uploading the document.
    if conversation is not None or bot is not None:
        if conversation is None or bot is None:
            raise ValueError("Both conversation and bot are required.")

        if (
            conversation.user_id != user.pk
            or conversation.bot_id != bot.pk
            or bot.owner_id != user.pk
        ):
            raise PermissionError("Document ownership mismatch.")

    data = generate_document(title, content, file_format)
    stored = upload_document(data, file_format)

    # DOCUMENT_PERSISTENCE_V1
    # Production chat calls provide both conversation and bot.
    if conversation is not None or bot is not None:
        if conversation is None or bot is None:
            raise ValueError("Both conversation and bot are required.")

        from django.urls import reverse
        from .document_models import GeneratedDocument

        file_id = stored["file_id"]
        # DOCUMENT_UPLOAD_ROLLBACK_V1
        try:
            document = GeneratedDocument.objects.create(
                owner=user,
                bot=bot,
                conversation=conversation,
                object_key="generated-documents/" + file_id,
                filename="document." + file_format,
                file_format=file_format,
                size_bytes=stored["size_bytes"],
            )
        except Exception:
            # Remove the newly uploaded R2 object if DB persistence fails.
            # Keep the database error as the primary exception.
            try:
                import os
                from .document_storage import _client
                bucket = os.environ.get('R2_BUCKET_NAME')
                if not bucket:
                    raise RuntimeError('R2 bucket is not configured.')
                _client().delete_object(
                    Bucket=bucket,
                    Key='generated-documents/' + file_id,
                )
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    'Failed to remove orphaned generated document from R2.'
                )
            raise

        return {
            "document_id": str(document.pk),
            "file_id": file_id,
            "title": title,
            "format": file_format,
            "size_bytes": stored["size_bytes"],
            "download_url": reverse(
                "bots:saved-document-download",
                kwargs={"document_id": document.pk},
            ),
        }

    # Legacy unit-test compatibility. Production chat always
    # supplies conversation and bot.
    # Never expose the raw R2 presigned URL in the chat response.
    download_path = create_document_download(
        user,
        stored["file_id"],
    )

    return {
        "file_id": stored["file_id"],
        "title": title,
        "format": file_format,
        "size_bytes": stored["size_bytes"],
        "download_url": download_path,
    }
