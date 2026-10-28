"""U6.3 authenticated audio delivery."""

from uuid import UUID

from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from ai_assistant.tts.errors import AuthorizationDenied

from .audio_store_bridge import retrieve_voice_audio
from .models import VoiceTurn
from .service import VoiceAccessDenied, _session, _uuid


@require_GET
def voice_turn_audio(request, session_id, request_id):
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

    if (
        turn.state != VoiceTurn.State.COMPLETED
        or turn.assistant_message_id is None
    ):
        return JsonResponse(
            {"error": "Audio is not ready."},
            status=409,
        )

    try:
        if isinstance(getattr(turn, "output_audio_key", None), UUID):
            from .free_voice_chain import retrieve_chain_audio
            audio = retrieve_chain_audio(user=request.user, session_id=session_id, turn=turn)
        else:
            audio = retrieve_voice_audio(
                user=request.user,
                assistant_id=session.assistant_id,
                voice_request_id=turn.request_id,
            )
    except AuthorizationDenied:
        return JsonResponse(
            {"error": "Audio not found."},
            status=404,
        )
    except Exception:
        # Never expose storage details or return audio on failure.
        return JsonResponse(
            {"error": "Audio delivery unavailable."},
            status=503,
        )

    if audio is None:
        return JsonResponse(
            {"error": "Audio delivery unavailable."},
            status=503,
        )

    # Accept only an MP3 signature from the configured TTS provider.
    is_mp3 = (
        isinstance(audio, bytes)
        and len(audio) >= 4
        and (
            audio.startswith(b"ID3")
            or (
                audio[0] == 0xFF
                and (audio[1] & 0xE0) == 0xE0
                and (audio[1] & 0x06) != 0
                and (audio[2] & 0xF0) != 0xF0
            )
        )
    )
    if not is_mp3:
        return JsonResponse(
            {"error": "Playable audio unavailable."},
            status=503,
        )

    response = HttpResponse(audio, content_type="audio/mpeg")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
