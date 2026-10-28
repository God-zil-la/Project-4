"""Authenticated WAV validation for U6.3.

This endpoint does not dispatch STT or charge quota.
Uploaded audio is not persisted by this endpoint.
"""

import hashlib
import os

from django.core.files.uploadedfile import SimpleUploadedFile

from .u63_mobile_audio_adapter import (
    U63MobileAudioError,
    normalize_u63_mobile_audio,
)

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from ai_assistant.stt.audio import validated_wav, InvalidAudio

from .service import _session, VoiceAccessDenied, VoiceConflict
from .turn_prepare import prepare_voice_turn
from .trusted_http_dispatch import (
    TrustedVoiceDependencies,
    dispatch_trusted_http_voice,
)
from .trusted_http_dispatch import serialize_voice_dispatch_result
from .server_dependencies import resolve_http_voice_dependencies


@require_POST
def upload_voice_audio(request, session_id):
    if not request.user.is_authenticated:
        return JsonResponse(
            {"error": "Authentication required."},
            status=401,
        )

    try:
        session = _session(request.user, session_id)
    except (VoiceAccessDenied, VoiceConflict, ValueError, TypeError):
        return JsonResponse(
            {"error": "Session not found."},
            status=404,
        )

    if not session.active:
        return JsonResponse(
            {"error": "Voice session is closed."},
            status=409,
        )

    upload = request.FILES.get("audio")

    if upload is None:
        return JsonResponse(
            {"error": "Audio file required."},
            status=400,
        )

    # Reject oversized uploads before decoding.
    if upload.size > 10 * 1024 * 1024:
        return JsonResponse(
            {"error": "Audio file too large."},
            status=413,
        )

    try:
        # Disabled by default. Enable only after security and
        # deployment-environment verification.
        mobile_conversion_enabled = (
            os.environ.get(
                "U63_MOBILE_AUDIO_CONVERSION_ENABLED",
                "false",
            ).lower() == "true"
        )

        if mobile_conversion_enabled:
            normalized_bytes = normalize_u63_mobile_audio(
                upload.read()
            )

            upload = SimpleUploadedFile(
                name="u63_recording.wav",
                content=normalized_bytes,
                content_type="audio/wav",
            )

        with validated_wav(upload) as audio:
            request_id = request.POST.get("request_id")

            if request_id and request.POST.get("process_voice") == "true":
                from .free_voice_chain import execute_voice_chain, VoiceChainUnavailable
                try:
                    result = execute_voice_chain(user=request.user, session_id=session.public_id,
                        request_id=request_id, audio=audio)
                except VoiceChainUnavailable as exc:
                    return JsonResponse({"error": str(exc)}, status=503)
                except (VoiceAccessDenied, VoiceConflict):
                    return JsonResponse({"error": "Voice session or request is unavailable."}, status=409)
                return JsonResponse({"session_id": str(session.public_id),
                    "request_id": str(request_id), "result": result})

            if request_id:
                # Server-controlled dependencies only.
                # No HTTP parameter can enable paid provider calls.
                # The Block D client only prepares turns, even if local provider
                # dependencies were enabled separately in this environment.
                dependencies = (None if request.POST.get("prepare_only") == "true"
                                else resolve_http_voice_dependencies(request=request))

                if dependencies is not None:
                    if not isinstance(
                        dependencies,
                        TrustedVoiceDependencies,
                    ):
                        return JsonResponse(
                            {"error": "Invalid server voice configuration."},
                            status=503,
                        )

                    try:
                        result = dispatch_trusted_http_voice(
                            user=request.user,
                            session_id=session.public_id,
                            request_id=request_id,
                            audio=audio,
                            dependencies=dependencies,
                        )
                    except (VoiceAccessDenied, VoiceConflict) as exc:
                        return JsonResponse(
                            {"error": str(exc)},
                            status=409,
                        )

                    return JsonResponse({
                        "session_id": str(session.public_id),
                        "request_id": request_id,
                        "result": serialize_voice_dispatch_result(result),
                    })

                try:
                    turn, created = prepare_voice_turn(
                        user=request.user,
                        session_id=session.public_id,
                        request_id=request_id,
                        audio=audio,
                    )
                except (VoiceAccessDenied, VoiceConflict) as exc:
                    return JsonResponse(
                        {"error": str(exc)},
                        status=409,
                    )

                return JsonResponse({
                    "state": turn.state,
                    "session_id": str(session.public_id),
                    "request_id": str(turn.request_id),
                    "created": created,
                    "audio_sha256": audio.sha256,
                    "duration_ms": audio.milliseconds,
                    "message": "Voice turn prepared. STT dispatch disabled.",
                })

            return JsonResponse({
                "state": "validated",
                "session_id": str(session.public_id),
                "audio_sha256": audio.sha256,
                "duration_ms": audio.milliseconds,
                "message": "Audio validated. STT dispatch is disabled.",
            })
    except U63MobileAudioError:
        return JsonResponse(
            {"error": "Unsupported or invalid mobile audio."},
            status=400,
        )
    except InvalidAudio:
        return JsonResponse(
            {"error": "Invalid WAV audio."},
            status=400,
        )
