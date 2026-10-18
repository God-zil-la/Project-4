import os

from django.db.models import F
from django.shortcuts import get_object_or_404

from rest_framework.authentication import (
    SessionAuthentication,
    TokenAuthentication,
)
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .document_models import GeneratedDocument
from .document_storage import _client


@api_view(["GET"])
@authentication_classes([
    TokenAuthentication,
    SessionAuthentication,
])
@permission_classes([IsAuthenticated])
def mobile_document_link(request, document_id):
    """Return a temporary R2 URL to an authenticated document owner."""

    document = get_object_or_404(
        GeneratedDocument,
        pk=document_id,
        owner=request.user,
        bot__owner=request.user,
        conversation__user=request.user,
        conversation__bot_id=F("bot_id"),
    )

    bucket = os.environ.get("R2_BUCKET_NAME")
    if not bucket:
        return Response(
            {"error": "Document storage is unavailable."},
            status=503,
        )

    signed_url = _client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": document.object_key,
            "ResponseContentDisposition": (
                'attachment; filename="'
                + document.filename
                + '"'
            ),
        },
        ExpiresIn=60,
    )

    response = Response({
        "document_id": str(document.pk),
        "filename": document.filename,
        "format": document.file_format,
        "download_url": signed_url,
        "expires_in": 60,
    })
    response["Cache-Control"] = "no-store"
    return response
