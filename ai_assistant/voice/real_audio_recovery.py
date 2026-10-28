"""U6.3 recovery of previously stored real MP3.

Never dispatches a provider or synthesizes audio.
"""

from dataclasses import dataclass

from ai_assistant.tts.models import TTSRequest
from ai_assistant.tts.message_access import get_assistant_message
from ai_assistant.tts.audio_retrieval import retrieve_audio

from . import service as voice_service
from .models import VoiceTurn
from .real_tts_identity import validate_real_tts_identity
from .mp3_validation import validate_live_mp3


class RealAudioRecoveryError(RuntimeError):
    pass


@dataclass(frozen=True)
class RealAudioRecoveryResult:
    state: str
    request_id: object
    audio_available: bool


def recover_real_voice_audio(
    *,
    user,
    session_id,
    request_id,
    audio_store,
):
    if audio_store is None:
        raise RealAudioRecoveryError("audio_store_required")

    session = voice_service._session(user, session_id)

    turn = VoiceTurn.objects.filter(
        session=session,
        request_id=voice_service._uuid(request_id),
    ).first()

    if turn is None:
        raise RealAudioRecoveryError("voice_turn_not_found")

    if turn.assistant_message_id is None:
        raise RealAudioRecoveryError("saved_answer_required")

    if turn.state not in {
        VoiceTurn.State.SYNTHESIZING,
        VoiceTurn.State.COMPLETED,
    }:
        raise RealAudioRecoveryError("recovery_not_available")

    text = get_assistant_message(
        user=user,
        assistant_id=session.assistant_id,
        conversation_id=session.conversation.public_id,
        message_id=turn.assistant_message_id,
    )

    key, fingerprint = validate_real_tts_identity(
        text=text,
        assistant_id=session.assistant_id,
        conversation_id=session.conversation.public_id,
        message_id=turn.assistant_message_id,
        request_id=turn.request_id,
    )

    row = TTSRequest.objects.filter(
        account__user_id=user.pk,
        assistant_id=session.assistant_id,
        request_id=key,
        fingerprint=fingerprint,
        state="succeeded",
    ).first()

    if row is None:
        return RealAudioRecoveryResult(
            state=str(turn.state),
            request_id=turn.request_id,
            audio_available=False,
        )

    audio = retrieve_audio(
        user=user,
        assistant_id=session.assistant_id,
        request_id=key,
        store=audio_store,
    )

    if audio is None:
        return RealAudioRecoveryResult(
            state=str(turn.state),
            request_id=turn.request_id,
            audio_available=False,
        )

    validate_live_mp3(audio)

    if turn.state == VoiceTurn.State.SYNTHESIZING:
        voice_service.advance_turn(
            user=user,
            session_id=session.public_id,
            request_id=turn.request_id,
            expected=VoiceTurn.State.SYNTHESIZING,
            target=VoiceTurn.State.COMPLETED,
        )

    return RealAudioRecoveryResult(
        state=VoiceTurn.State.COMPLETED,
        request_id=turn.request_id,
        audio_available=True,
    )
