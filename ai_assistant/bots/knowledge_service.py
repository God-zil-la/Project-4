"""Shared synchronous upload pipeline. No external calls under the quota lock."""
import logging

from django.conf import settings
from django.db import transaction

from ai_assistant.accounts.models import UserProfile
from ai_assistant.accounts.plan_utils import get_knowledge_storage_status
from ai_assistant.dashboard.models import BotUsageLog
from .knowledge_errors import KnowledgeProcessingError, KnowledgeQuotaError
from .knowledge_utils import generate_embedding_batches
from .models import KnowledgeBase, KnowledgeChunk
from .utils import chunk_text, extract_text, validate_extracted_text

logger = logging.getLogger(__name__)


def _check_quota(user, source_size):
    storage = get_knowledge_storage_status(user, incoming_size_bytes=source_size)
    if not storage["allowed"]:
        raise KnowledgeQuotaError(storage)


def upload_knowledge(user, bot, file=None, manual_text=""):
    if bot.owner_id != user.pk:
        raise PermissionError("Knowledge must belong to the uploading user.")
    source_size = file.size if file is not None else len(manual_text.encode("utf-8"))
    _check_quota(user, source_size)
    if source_size > settings.KNOWLEDGE_MAX_FILE_BYTES:
        raise KnowledgeProcessingError(
            "File exceeds the Knowledge processing size limit.", "processing_limit", 413
        )
    source = extract_text(file, file.name) if file is not None else manual_text
    validate_extracted_text(source)
    chunks = chunk_text(source)
    if len(chunks) > settings.KNOWLEDGE_MAX_CHUNKS:
        raise KnowledgeProcessingError(
            "Document produces too many Knowledge chunks.", "processing_limit", 413
        )

    def record_usage(usage):
        if usage["tokens_used"] > 0:
            BotUsageLog.objects.create(user=user, bot=bot, **usage)

    try:
        embeddings = generate_embedding_batches(chunks, record_usage=record_usage)
        prepared = list(zip(chunks, embeddings, strict=True))
    except Exception as error:
        logger.exception("Knowledge embedding failed for bot %s", bot.pk)
        raise KnowledgeProcessingError(
            "Failed to process file: embedding service unavailable. Please try again.",
            "embedding_failed", 503,
        ) from error

    if file is not None:
        file.seek(0)
    kb = KnowledgeBase(bot=bot, file=file, uploaded_by=user, source_size_bytes=source_size)
    try:
        with transaction.atomic():
            # Every web/API writer locks the same account row, then rereads usage.
            profile = UserProfile.objects.select_for_update().get(user=user)
            user.profile = profile
            _check_quota(user, source_size)
            kb.save()
            for text, embedding in prepared:
                KnowledgeChunk.objects.create(
                    knowledge_file=kb, text=text, embedding=embedding
                )
    except KnowledgeQuotaError:
        raise
    except Exception as error:
        if kb.file and kb.file._committed:
            try:
                kb.file.delete(save=False)
            except Exception:
                logger.exception("Failed to clean up Knowledge upload for bot %s", bot.pk)
        logger.exception("Knowledge storage failed for bot %s", bot.pk)
        raise KnowledgeProcessingError(
            "Failed to process file: could not save Knowledge. Please try again.",
            "storage_failed", 503,
        ) from error
    return kb
