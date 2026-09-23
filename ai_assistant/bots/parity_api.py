"""Token-authenticated adapters for existing web features; no new data model."""
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.views import APIView
from ai_assistant.dashboard.views import dashboard_data
from .forms import KnowledgeBaseForm
from .models import Bot, KnowledgeBase
from .knowledge_service import upload_knowledge
from .knowledge_errors import KnowledgeProcessingError, KnowledgeQuotaError
from .views import analytics_data


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
        try:
            kb = upload_knowledge(request.user, bot, file=file)
        except KnowledgeProcessingError as error:
            data = {"error": str(error), "code": error.code}
            if isinstance(error, KnowledgeQuotaError):
                data["plan"] = error.storage["plan"]
            return Response(data, status=error.status)
        return Response(knowledge_row(kb), status=201)

class KnowledgeDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, bot_id, knowledge_id):
        item = get_object_or_404(KnowledgeBase, pk=knowledge_id,
                                bot_id=bot_id, bot__owner=request.user)
        # Reuse the existing deletion signal and retry queue for stored files.
        item.delete()
        return Response(status=204)
