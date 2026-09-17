"""Token-authenticated adapters for existing web features; no new data model."""
import logging
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from ai_assistant.accounts.plan_utils import get_knowledge_storage_status
from ai_assistant.dashboard.models import BotUsageLog
from ai_assistant.dashboard.views import dashboard_data
from .forms import KnowledgeBaseForm
from .models import Bot, KnowledgeBase, KnowledgeChunk
from .utils import extract_text, chunk_text
from .knowledge_utils import generate_embedding_batches
from .views import analytics_data

logger = logging.getLogger(__name__)

class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(dashboard_data(request.user))

class AnalyticsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        bot_data, time_data = analytics_data(request.user)
        return Response({"bot_data": bot_data, "time_data": time_data})

def knowledge_row(item):
    return {"id": item.id, "name": item.file.name.replace("knowledge_files/", "")
            if item.file else "Manual Knowledge"}

class KnowledgeAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get(self, request, bot_id):
        bot = get_object_or_404(Bot, pk=bot_id, owner=request.user)
        return Response({"files": [knowledge_row(item) for item in
                         KnowledgeBase.objects.filter(bot=bot).order_by("-id")]})

    def post(self, request, bot_id):
        bot = get_object_or_404(Bot, pk=bot_id, owner=request.user)
        # The current web UI exposes document upload only. Do not add a new text editor.
        form = KnowledgeBaseForm({}, request.FILES)
        if not form.is_valid():
            return Response({"errors": dict(form.errors)}, status=400)
        file = form.cleaned_data["file"]
        storage = get_knowledge_storage_status(request.user, incoming_size_bytes=file.size)
        if not storage["allowed"]:
            return Response({"error": "Knowledge storage limit reached.",
                             "plan": storage["plan"]}, status=403)
        kb = None
        try:
            source = extract_text(file, file.name)
            if not source.strip():
                return Response({"error": "No valid content extracted from input."}, status=400)
            chunks = chunk_text(source)
            if not chunks:
                raise ValueError("No valid knowledge chunks were generated.")
            def record_usage(usage):
                if usage["tokens_used"] > 0:
                    BotUsageLog.objects.create(user=request.user, bot=bot, **usage)
            embeddings = generate_embedding_batches(chunks, record_usage=record_usage)
            file.seek(0)
            kb = KnowledgeBase(bot=bot, file=file, uploaded_by=request.user,
                               source_size_bytes=file.size)
            with transaction.atomic():
                # Serialize native uploads for this account and recheck after processing.
                type(request.user.profile).objects.select_for_update().get(user=request.user)
                storage = get_knowledge_storage_status(request.user, incoming_size_bytes=file.size)
                if not storage["allowed"]:
                    return Response({"error": "Knowledge storage limit reached."}, status=403)
                kb.save()
                for chunk, embedding in zip(chunks, embeddings, strict=True):
                    KnowledgeChunk.objects.create(knowledge_file=kb, text=chunk, embedding=embedding)
        except Exception:
            if kb is not None and kb.file and kb.file._committed:
                try:
                    kb.file.delete(save=False)
                except Exception:
                    logger.exception("Failed to clean up native knowledge upload")
            logger.exception("Native knowledge processing failed")
            return Response({"error": "Failed to process file. Please check the content and try again."}, status=400)
        return Response(knowledge_row(kb), status=201)

class KnowledgeDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, bot_id, knowledge_id):
        item = get_object_or_404(KnowledgeBase, pk=knowledge_id,
                                bot_id=bot_id, bot__owner=request.user)
        # Reuse the existing deletion signal and retry queue for stored files.
        item.delete()
        return Response(status=204)
