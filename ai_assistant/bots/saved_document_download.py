from django.db import models
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect

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

from .document_models import GeneratedDocument
from .document_storage import _client

import os


@api_view(["GET"])
@authentication_classes([
    TokenAuthentication,
    SessionAuthentication,
])
@permission_classes([IsAuthenticated])
def download_saved_document(request, document_id):
    """
    Reissue a short-lived URL for a document owned by the user.
    """
    document = get_object_or_404(
        GeneratedDocument,
        pk=document_id,
        owner=request.user,
        bot__owner=request.user,
        conversation__user=request.user,
        conversation__bot_id=models.F("bot_id"),
    )

    bucket = os.environ.get("R2_BUCKET_NAME")
    if not bucket:
        raise RuntimeError("R2 bucket is not configured.")

    url = _client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": document.object_key,
            "ResponseContentDisposition": (
                f'attachment; filename="{document.filename}"'
            ),
        },
        ExpiresIn=60,
    )

    response = HttpResponseRedirect(url)
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response


@api_view(["GET"])
@authentication_classes([
    TokenAuthentication,
    SessionAuthentication,
])
@permission_classes([IsAuthenticated])
def get_saved_document_download_url(request, document_id):
    """Return a fresh, short-lived URL for the document owner."""
    from rest_framework.response import Response

    document = get_object_or_404(
        GeneratedDocument,
        pk=document_id,
        owner=request.user,
        bot__owner=request.user,
        conversation__user=request.user,
        conversation__bot_id=models.F("bot_id"),
    )

    bucket = os.environ.get("R2_BUCKET_NAME")
    if not bucket:
        raise RuntimeError("R2 bucket is not configured.")

    url = _client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": document.object_key,
            "ResponseContentDisposition": (
                f'attachment; filename="{document.filename}"'
            ),
        },
        ExpiresIn=60,
    )

    response = Response({
        "download_url": url,
        "filename": document.filename,
        "expires_in": 60,
    })
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response
