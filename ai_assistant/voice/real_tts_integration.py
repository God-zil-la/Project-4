"""U6.3 isolated real-TTS integration.

No automatic retries after dispatch.
No paid provider is activated here.
"""

from dataclasses import dataclass

from ai_assistant.tts import service as tts_service
from ai_assistant.tts.message_access import get_assistant_message

from .real_tts_request import prepare_real_tts_request
from .real_tts_identity import validate_real_tts_identity
from .real_audio_storage import store_live_voice_mp3
from .mp3_validation import validate_live_mp3


class LiveTTSIntegrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveTTSResult:
    state: str
    request_id: object
    audio_available: bool


def execute_isolated_live_tts(
    *,
    user,
    assistant_id,
    conversation_id,
    message_id,
    request_id,
    audio_store,
    synthesize,
):
    if audio_store is None:
        raise LiveTTSIntegrationError("audio_store_required")

    if not callable(synthesize):
        raise LiveTTSIntegrationError("synthesizer_required")

    row = prepare_real_tts_request(
        user=user,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )

    claimed = tts_service.claim(
        user=user,
        assistant_id=assistant_id,
        row_id=row.pk,
    )

    if not claimed:
        row.refresh_from_db()

        return LiveTTSResult(
            state=row.state,
            request_id=row.request_id,
            audio_available=False,
        )

    # From this point, never automatically retry synthesis.

    text = get_assistant_message(
        user=user,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
    )

    _, current_fingerprint = validate_real_tts_identity(
        text=text,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
    )

    if current_fingerprint != row.fingerprint:
        tts_service.finish(
            user_id=user.pk,
            row_id=row.pk,
            state="not_processed",
        )

        raise LiveTTSIntegrationError("saved_answer_changed")

    audio = validate_live_mp3(synthesize(text))

    store_live_voice_mp3(
        user=user,
        assistant_id=assistant_id,
        conversation_id=conversation_id,
        message_id=message_id,
        request_id=request_id,
        audio=audio,
        store=audio_store,
    )

    return LiveTTSResult(
        state="succeeded",
        request_id=row.request_id,
        audio_available=True,
    )
