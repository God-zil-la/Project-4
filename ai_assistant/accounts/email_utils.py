"""Canonical email links and sanitized delivery failures."""
import logging
from urllib.parse import urlsplit
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def public_origin(request=None):
    origin = settings.PUBLIC_BASE_URL.rstrip("/")
    if not origin and settings.DEBUG and request is not None:
        origin = request.build_absolute_uri("/").rstrip("/")
    parts = urlsplit(origin)
    if (parts.scheme not in {"http", "https"} or not parts.hostname
            or parts.username or parts.password or parts.path or parts.query or parts.fragment
            or (not settings.DEBUG and parts.scheme != "https")):
        raise ImproperlyConfigured("PUBLIC_BASE_URL must be the canonical HTTPS origin in production.")
    return origin


def send_account_email(message):
    try:
        if message.send(fail_silently=False) != 1:
            raise RuntimeError("Email backend did not accept the message")
        return True
    except Exception:
        logger.error("Account email delivery failed; check the configured email backend.")
        return False
