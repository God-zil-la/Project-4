"""Authentication boundary for U6.3 voice endpoints."""

from io import BytesIO

from django.http import HttpResponse
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


MAX_VOICE_REQUEST_BYTES = 12 * 1024 * 1024


def authenticated_voice_view(view, methods):
    @api_view(methods)
    @authentication_classes([
        TokenAuthentication,
        SessionAuthentication,
    ])
    @permission_classes([IsAuthenticated])
    def endpoint(request, *args, **kwargs):
        django_request = request._request

        if django_request.method == "POST":
            import logging

            logger = logging.getLogger("django.request")
            logger.warning(
                "U63_DIAG path=%s content_length=%s "
                "body_cached=%s stream_read_started=%s",
                django_request.path,
                django_request.META.get("CONTENT_LENGTH"),
                hasattr(django_request, "_body"),
                getattr(django_request, "_read_started", False),
            )

        if django_request.method == "POST":
            content_length = django_request.META.get(
                "CONTENT_LENGTH", ""
            )

            try:
                declared_size = int(content_length)
            except (TypeError, ValueError):
                declared_size = -1

            if declared_size > MAX_VOICE_REQUEST_BYTES:
                return HttpResponse(
                    "Voice request too large.",
                    status=413,
                )

            if (
                django_request.path.endswith("/start/")
                and "application/json" in
                django_request.META.get("CONTENT_TYPE", "").lower()
            ):
                import json

                parsed = request.data
                if not isinstance(parsed, dict):
                    parsed = {}

                data = json.dumps(parsed).encode("utf-8")

                if len(data) > MAX_VOICE_REQUEST_BYTES:
                    return HttpResponse(
                        "Voice request too large.",
                        status=413,
                    )

                django_request._body = data
                django_request._stream = BytesIO(data)

            elif not hasattr(django_request, "_body"):
                stream = django_request._stream
                data = stream.read(MAX_VOICE_REQUEST_BYTES + 1)

                if len(data) > MAX_VOICE_REQUEST_BYTES:
                    return HttpResponse(
                        "Voice request too large.",
                        status=413,
                    )

                django_request._body = data
                django_request._stream = BytesIO(data)
        return view(django_request, *args, **kwargs)

    return endpoint
