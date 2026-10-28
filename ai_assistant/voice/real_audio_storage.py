"""U6.3 storage bridge for validated real MP3 audio."""

from ai_assistant.tts.audio_finalization import finalize_stored_audio
from ai_assistant.tts.message_access import get_assistant_message
from .real_tts_identity import validate_real_tts_identity
from ai_assistant.tts.models import TTSRequest
from ai_assistant.tts.authorization import authorize

from .mp3_validation import validate_live_mp3


def store_live_voice_mp3(
    *,
    user,
    assistant_id,
    conversation_id,
    message_id,
    request_id,
    audio,
    store,
):
    """Store MP3 only for an authorized, identity-bound TTS request."""

    if store is None:
        raise ValueError("audio_store_required")

    audio = validate_live_mp3(audio)

    text = get_assistant_message(
        user=user,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )

    key, fingerprint = validate_real_tts_identity(
        text=text,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )

    row = TTSRequest.objects.filter(
        account__user_id=user.pk,
        assistant_id=assistant_id,
        request_id=key,
        fingerprint=fingerprint,
        state="dispatched",
    ).first()

    if row is None:
        raise ValueError("tts_request_identity_mismatch")

    authorize(user, assistant_id)

    finalize_stored_audio(
        user_id=user.pk,
        row_id=row.pk,
        request_id=row.request_id,
        audio=audio,
        store=store,
    )

    return row.request_id
