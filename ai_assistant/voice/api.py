"""Authenticated U6.3 session lifecycle; never dispatches external providers."""

from django.utils import timezone

import json

from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .service import expire_voice_session
from .models import VoiceSession
from .service import (
    VoiceAccessDenied,
    VoiceConflict,
    _session,
    start_session,
    stop_session,
)


def _error(message, status):
    return JsonResponse({"error": message}, status=status)


def _session_response(session, *, status=200):
    """Expose a server observation; never accept a client clock or charge."""
    from .live_session_timer import timer_snapshot
    observed = timezone.now()
    remaining = 0
    reservation = session.quota_reservation
    if session.active and reservation is not None:
        remaining = timer_snapshot(
            started_at=session.started_at,
            reserved_ms=reservation.duration_ms,
            observed_at=max(observed, session.started_at),
            monthly_period_end=reservation.usage.period_end,
        ).remaining_ms
    response = JsonResponse({
        "session_id": str(session.public_id),
        "assistant_id": session.assistant_id,
        "conversation_id": str(session.conversation.public_id),
        "active": session.active and remaining > 0,
        "server_time": observed.isoformat(),
        "deadline_at": session.deadline_at.isoformat() if session.deadline_at else None,
        "remaining_ms": remaining,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
    }, status=status)
    response["Cache-Control"] = "no-store"
    return response


@require_http_methods(["POST"])
def start_voice(request):
    if not request.user.is_authenticated:
        return _error("Authentication required.", 401)

    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return _error("Invalid JSON.", 400)

    if not isinstance(payload, dict):
        return _error("Invalid JSON object.", 400)

    assistant_id = payload.get("assistant_id")
    conversation_id = payload.get("conversation_id")

    if not assistant_id or not conversation_id:
        return _error("Assistant and conversation required.", 400)

    try:
        from ai_assistant.bots.models import Bot, Conversation

        assistant = Bot.objects.filter(
            pk=assistant_id,
        ).first()

        conversation = Conversation.objects.filter(
            public_id=conversation_id,
        ).first()

        if assistant is None or conversation is None:
            return _error("Voice session not found.", 404)

        session = start_session(
            user=request.user,
            assistant=assistant,
            conversation=conversation,
            request_id=payload.get("request_id"),
        )
    except ValidationError:
        return _error("Invalid voice identifier.", 400)
    except VoiceAccessDenied:
        return _error("Access denied.", 403)
    except (VoiceConflict, ValueError, TypeError):
        return _error("Invalid voice session.", 409)

    return _session_response(session, status=201)


@csrf_protect
@require_http_methods(["GET"])
def voice_status(request, session_id):
    if not request.user.is_authenticated:
        return _error("Authentication required.", 401)

    try:
        session = VoiceSession.objects.get(public_id=session_id, user=request.user, conversation__user=request.user)
        # Block D must never mutate legacy sessions without reservations.
        if session.quota_reservation_id is None:
            return _error("Legacy voice session is not supported.", 409)
        expire_voice_session(user=request.user, session_id=session_id)
        session.refresh_from_db()
    except (VoiceSession.DoesNotExist, VoiceAccessDenied, VoiceConflict, ValueError, TypeError):
        return _error("Session not found.", 404)

    return _session_response(session)


@require_http_methods(["POST"])
def stop_voice(request, session_id):
    if not request.user.is_authenticated:
        return _error("Authentication required.", 401)

    session = VoiceSession.objects.filter(
        public_id=session_id,
        user=request.user,
        conversation__user=request.user,
    ).first()

    if session is None:
        return _error("Session not found.", 404)

    if session.quota_reservation_id is None:
        return _error("Legacy voice session is not supported.", 409)

    session = stop_session(user=request.user, session_id=session_id)

    return _session_response(session)
