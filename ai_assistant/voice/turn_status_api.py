"""Read-only U6.3 voice-turn status API."""

from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import VoiceTurn
from .service import VoiceAccessDenied, _session, _uuid


@require_GET
def voice_turn_status(request, session_id, request_id):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Authentication required."},
            status=401,
        )

    try:
        session = _session(request.user, session_id)
        turn = VoiceTurn.objects.filter(
            session=session,
            request_id=_uuid(request_id),
        ).first()
    except VoiceAccessDenied:
        return JsonResponse(
            {"error": "Voice turn not found."},
            status=404,
        )

    if turn is None:
        return JsonResponse(
            {"error": "Voice turn not found."},
            status=404,
        )

    response = JsonResponse({
        "session_id": str(session.public_id),
        "request_id": str(turn.request_id),
        "state": turn.state,
        "has_transcript": bool(turn.transcript),
        "error_code": turn.error_code,
        "audio_available": bool(turn.output_audio_key and turn.state == VoiceTurn.State.COMPLETED),
        "has_assistant_answer": turn.assistant_message_id is not None,
    })
    response["Cache-Control"] = "no-store"
    return response
