import os
import re
import uuid
import boto3

from botocore.config import Config


FORMATS = {
    "pdf": ("application/pdf", ".pdf"),
    "docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document",
        ".docx",
    ),
    "xlsx": (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet",
        ".xlsx",
    ),
    "csv": ("text/csv; charset=utf-8", ".csv"),
}

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024


def _client():
    endpoint = os.environ.get("R2_ENDPOINT_URL")
    access_key = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")

    if not all((endpoint, access_key, secret_key)):
        raise RuntimeError("R2 storage is not configured.")

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def upload_document(data, file_format):
    """Upload a generated document privately and return a short-lived URL."""
    file_format = str(file_format).lower().strip()

    if file_format not in FORMATS:
        raise ValueError("Unsupported document format.")

    if not isinstance(data, bytes) or not data:
        raise ValueError("Document content must be non-empty bytes.")

    if len(data) > MAX_DOCUMENT_BYTES:
        raise ValueError("Document exceeds the 10 MB limit.")

    bucket = os.environ.get("R2_BUCKET_NAME")
    if not bucket:
        raise RuntimeError("R2 bucket is not configured.")

    content_type, extension = FORMATS[file_format]
    object_key = f"generated-documents/{uuid.uuid4().hex}{extension}"

    client = _client()
    client.put_object(
        Bucket=bucket,
        Key=object_key,
        Body=data,
        ContentType=content_type,
    )

    url = client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": object_key,
            "ResponseContentType": content_type,
        },
        ExpiresIn=900,
    )

    return {
        "file_id": object_key.rsplit("/", 1)[-1],
        "format": file_format,
        "size_bytes": len(data),
        "download_url": url,
        "expires_in": 900,
    }
