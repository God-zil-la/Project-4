"""Authenticated, idempotent flagging of accessible assistant responses."""
import math
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.exceptions import Throttled, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AIResponseReport, ChatMessage
from .request_validation import validate_request_object


class AIResponseReportAPIView(APIView):
    permission_classes = [IsAuthenticated]
    daily_limit = 20

    def post(self, request, conversation_id, message_id):
        validate_request_object(request.data)
        if request.data:
            raise ValidationError({"error": "Send an empty object to flag this response."})

        # Match the conversation history API's access boundary. Never trust
        # client-supplied response text, ownership, or report status.
        message = get_object_or_404(
            ChatMessage.objects.select_related("conversation"),
            pk=message_id,
            conversation__public_id=conversation_id,
            conversation__user=request.user,
            sender=ChatMessage.SENDER_ASSISTANT,
        )
        with transaction.atomic():
            # Serialize submissions per reporter across production workers.
            User.objects.select_for_update().get(pk=request.user.pk)
            existing = AIResponseReport.objects.filter(
                reporter=request.user, message=message,
            ).first()
            if existing:
                return Response({"id": existing.pk, "reported": True}, status=200)

            now = timezone.now()
            recent = AIResponseReport.objects.filter(
                reporter=request.user, created_at__gt=now - timedelta(days=1),
            ).order_by("created_at")
            if recent.count() >= self.daily_limit:
                wait = math.ceil((recent.first().created_at + timedelta(days=1) - now).total_seconds())
                raise Throttled(wait=max(1, wait), detail="Daily report limit reached. Please try again later.")

            report = AIResponseReport.objects.create(
                reporter=request.user,
                message=message,
                original_message_id=message.pk,
                conversation_id_snapshot=message.conversation.public_id,
                response_text=message.message,
                response_created_at=message.timestamp,
            )
        return Response({"id": report.pk, "reported": True}, status=201)
