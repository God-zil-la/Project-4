"""Authorization boundary for private U6.2 audio retrieval."""

from .authorization import authorize
from .errors import AuthorizationDenied
from .models import TTSRequest


def authorize_audio_request(*, user, assistant_id, request_id):
    """Return a TTS request only when it belongs to the authorized user."""
    user_id = authorize(user, assistant_id)

    row = TTSRequest.objects.filter(
        account__user_id=user_id,
        assistant_id=assistant_id,
        request_id=request_id,
    ).first()

    if row is None:
        raise AuthorizationDenied("tts_denied")

    return row
