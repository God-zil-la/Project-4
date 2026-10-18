import re

from django.core import signing
from django.urls import reverse

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

from django.http import HttpResponseRedirect, Http404

from .document_storage import _client
import os


TOKEN_SALT = "myaiassistant-document-download-v1"
TOKEN_MAX_AGE = 7 * 24 * 60 * 60

FILE_PATTERN = re.compile(
    r"^[0-9a-f]{32}\.(pdf|docx|xlsx|csv)$"
)


def create_document_download(user, file_id):
    """
    Create an owner-bound, expiring download path.

    Does not reveal R2 credentials or a permanent public URL.
    """
    if not FILE_PATTERN.fullmatch(str(file_id)):
        raise ValueError("Invalid document ID.")

    token = signing.dumps(
        {
            "owner": str(user.pk),
            "file_id": file_id,
        },
        salt=TOKEN_SALT,
    )

    return reverse(
        "bots:document-download",
        kwargs={"token": token},
    )


@api_view(["GET"])
@authentication_classes([
    TokenAuthentication,
    SessionAuthentication,
])
@permission_classes([IsAuthenticated])
def download_document(request, token):
    try:
        payload = signing.loads(
            token,
            salt=TOKEN_SALT,
            max_age=TOKEN_MAX_AGE,
        )
    except signing.BadSignature:
        raise Http404("Document not found.")

    if not isinstance(payload, dict):
        raise Http404("Document not found.")

    file_id = payload.get("file_id")

    if (
        str(payload.get("owner")) != str(request.user.pk)
        or not isinstance(file_id, str)
        or not FILE_PATTERN.fullmatch(file_id)
    ):
        raise Http404("Document not found.")

    bucket = os.environ.get("R2_BUCKET_NAME")

    if not bucket:
        raise RuntimeError("R2 bucket is not configured.")

    object_key = f"generated-documents/{file_id}"

    client = _client()

    url = client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": object_key,
            "ResponseContentDisposition": (
                f'attachment; filename="{file_id}"'
            ),
        },
        ExpiresIn=60,
    )

    response = HttpResponseRedirect(url)
    response["Cache-Control"] = "no-store"
    response["Referrer-Policy"] = "no-referrer"
    return response
