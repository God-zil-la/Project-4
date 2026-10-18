from django.shortcuts import get_object_or_404
from django.urls import reverse

from rest_framework.authentication import (
    TokenAuthentication,
    SessionAuthentication,
)
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Conversation
from .document_models import GeneratedDocument


@api_view(["GET"])
@authentication_classes([
    TokenAuthentication,
    SessionAuthentication,
])
@permission_classes([IsAuthenticated])
def conversation_documents(request, conversation_id):
    """List documents belonging to this user's conversation."""

    conversation = get_object_or_404(
        Conversation,
        public_id=conversation_id,
        user=request.user,
        bot__owner=request.user,
        is_widget=False,
    )

    documents = GeneratedDocument.objects.filter(
        owner=request.user,
        bot=conversation.bot,
        conversation=conversation,
    ).order_by("-created_at")

    result = [
        {
            "document_id": str(document.pk),
            "filename": document.filename,
            "format": document.file_format,
            "size_bytes": document.size_bytes,
            "created_at": document.created_at.isoformat(),
            "link_url": reverse(
                "bots:mobile-document-link",
                kwargs={"document_id": document.pk},
            ),
        }
        for document in documents
    ]

    response = Response({
        "conversation_id": str(conversation.public_id),
        "documents": result,
    })
    response["Cache-Control"] = "no-store"
    return response
