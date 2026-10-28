"""Isolated Cloudflare R2 AudioStore. No credential or client creation."""

from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID

from .audio_storage import AUDIO_TTL, MAX_AUDIO_BYTES, validate_audio


def _error_code(exc):
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return str(response.get("Error", {}).get("Code", ""))
    return ""


class R2AudioStore:
    def __init__(self, *, client, bucket):
        if not client or not isinstance(bucket, str) or not bucket:
            raise ValueError("invalid_storage_configuration")
        self.client = client
        self.bucket = bucket

    @staticmethod
    def _key(request_id):
        if not isinstance(request_id, UUID):
            raise ValueError("invalid_request_id")
        return f"tts/private/{request_id.hex}.audio"

    def save(self, *, request_id, audio, expires_at=None):
        validate_audio(audio)
        key = self._key(request_id)
        if expires_at is None:
            # Retained for standalone adapter tests. The durable wrapper
            # always passes the original request's immutable expiry.
            expires_at = datetime.now(timezone.utc) + AUDIO_TTL
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            raise ValueError("timezone_required")
        now = datetime.now(timezone.utc)
        if expires_at <= now or expires_at > now + AUDIO_TTL:
            raise ValueError("invalid_audio_expiry")
        expires_at = int(expires_at.timestamp())
        if expires_at <= int(now.timestamp()):
            raise ValueError("audio_expired")
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=audio,
                ContentType="application/octet-stream",
                Metadata={"expires-at": str(expires_at)},
                IfNoneMatch="*",
            )
        except Exception as exc:
            if _error_code(exc) in ("PreconditionFailed", "412"):
                # A conditional write rejection is not proof that the
                # pre-existing object has the same audio or expiry.
                existing = self.load(request_id=request_id, expected_expiry=expires_at)
                if existing is None or sha256(existing).digest() != sha256(audio).digest():
                    raise ValueError("existing_audio_conflict") from exc
                return
            raise

    def load(self, *, request_id, expected_expiry=None):
        key = self._key(request_id)
        try:
            response = self.client.get_object(
                Bucket=self.bucket,
                Key=key,
            )
        except Exception as exc:
            if _error_code(exc) in ("NoSuchKey", "NotFound", "404"):
                return None
            raise

        body = response.get("Body")
        try:
            metadata = response.get("Metadata") or {}
            try:
                expires_at = int(metadata["expires-at"])
            except (KeyError, TypeError, ValueError, OverflowError):
                return None

            if expected_expiry is not None:
                if isinstance(expected_expiry, datetime):
                    if expected_expiry.tzinfo is None:
                        raise ValueError("timezone_required")
                    expected_expiry = int(expected_expiry.timestamp())
                if type(expected_expiry) is not int or expires_at != expected_expiry:
                    return None

            now = datetime.now(timezone.utc).timestamp()
            if now >= expires_at:
                return None

            size = response.get("ContentLength")
            if not isinstance(size, int) or not 0 < size <= MAX_AUDIO_BYTES:
                return None

            if body is None:
                return None

            audio = body.read(MAX_AUDIO_BYTES + 1)
            if not isinstance(audio, bytes) or len(audio) != size:
                return None

            if datetime.now(timezone.utc).timestamp() >= expires_at:
                return None

            return audio
        finally:
            if body is not None:
                close = getattr(body, "close", None)
                if callable(close):
                    close()

    def delete(self, *, request_id):
        self.client.delete_object(
            Bucket=self.bucket,
            Key=self._key(request_id),
        )
