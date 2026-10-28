"""Authenticated TTS API. Not routed or deployed."""
from uuid import UUID

from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .errors import AuthorizationDenied, Conflict, InvalidInput, TTSError
from .saved_synthesis import synthesize_saved_response


class SavedResponseTTSAPIView(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data

        if not isinstance(data, dict):
            return Response({"error": "invalid_request"}, status=400)

        if set(data) != {
            "assistant_id", "conversation_id", "message_id", "request_id"
        }:
            return Response({"error": "invalid_request"}, status=400)

        assistant_id = data["assistant_id"]
        message_id = data["message_id"]

        if (
            type(assistant_id) is not int
            or assistant_id <= 0
            or type(message_id) is not int
            or message_id <= 0
        ):
            return Response({"error": "invalid_request"}, status=400)

        try:
            conversation_id = UUID(str(data["conversation_id"]))
            request_id = UUID(str(data["request_id"]))
        except (ValueError, TypeError, AttributeError):
            return Response({"error": "invalid_request"}, status=400)

        try:
            result = synthesize_saved_response(
                user=request.user,
                assistant_id=assistant_id,
                conversation_id=conversation_id,
                message_id=message_id,
                request_id=request_id,
            )
        except AuthorizationDenied:
            return Response({"error": "tts_denied"}, status=403)
        except InvalidInput:
            return Response({"error": "invalid_request"}, status=400)
        except Conflict:
            return Response({"error": "tts_conflict"}, status=409)
        except TTSError:
            return Response({"error": "tts_unavailable"}, status=503)
        except Exception:
            return Response({"error": "tts_unavailable"}, status=503)

        # Mock audio is deliberately not playable and must never be
        # represented to a client as a real MP3.
        return Response({
            "request_id": str(result.request_id),
            "state": result.state,
            "audio_available": False,
        }, status=200 if result.state == "succeeded" else 202)
