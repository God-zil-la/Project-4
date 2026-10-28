"""Free U6.3 voice chain. No provider is installed or enabled by import."""
import logging

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from hashlib import sha256
from uuid import uuid4

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .ai_adapter import process_voice_answer
from .provider_guard import mock_ai_provider
from .live_free_entitlement import require_free_voice_access
from .local_audio_store import LocalVoiceAudioStore
from .models import VoiceTurn
from .mp3_validation import validate_live_mp3
from .service import (
    VoiceAccessDenied, VoiceConflict, _session, _uuid,
    claim_tts_dispatch, save_transcript,
)
from .turn_prepare import prepare_voice_turn


class VoiceChainUnavailable(VoiceConflict):
    pass


@dataclass(frozen=True)
class VoiceChainProviders:
    transcribe: object
    synthesize: object
    external_calls: bool = False
    mock_ai: object = None


logger = logging.getLogger(__name__)

_providers = ContextVar("u63_voice_chain_providers", default=None)


@contextmanager
def voice_chain_providers(providers):
    """Trusted server/test composition, isolated per execution context."""
    if not isinstance(providers, VoiceChainProviders):
        raise VoiceChainUnavailable("Invalid voice providers.")
    token = _providers.set(providers)
    try:
        yield
    finally:
        _providers.reset(token)


def configured_providers():
    providers = _providers.get()
    if providers is None or not callable(providers.transcribe) or not callable(providers.synthesize):
        raise VoiceChainUnavailable("Voice processing is not configured. No external calls were made.")
    # This block does not grant external-cost approval. Local test composition
    # must replace every external AI/KB boundary while using the existing engine.
    if providers.external_calls:
        raise VoiceChainUnavailable("External voice calls require a separately approved integration.")
    if not (settings.DEBUG and getattr(settings, "U63_VOICE_TEST_DOUBLES", False)):
        raise VoiceChainUnavailable("Local voice test doubles are disabled.")
    if not callable(providers.mock_ai):
        raise VoiceChainUnavailable("Explicit local mock AI provider required.")
    return providers


def guard(user, session_id):
    session = _session(user, session_id)
    require_free_voice_access(user=user)
    if not session.quota_reservation_id:
        raise VoiceAccessDenied("Reserved Free session required.")
    reservation = session.quota_reservation
    if (reservation.state != "reserved" or reservation.user_id != user.pk
            or reservation.usage.user_id != user.pk):
        raise VoiceAccessDenied("Active session reservation required.")
    if not session.deadline_at or timezone.now() >= session.deadline_at:
        raise VoiceAccessDenied("Voice deadline reached before stage dispatch.")
    return session


@transaction.atomic
def claim_transcription(*, user, session_id, request_id, audio):
    guard(user, session_id)
    session = _session(user, session_id, lock=True)
    # Serialize different request identities too, so one session cannot fan out
    # concurrent STT/AI/TTS work or reorder its conversation history.
    if VoiceTurn.objects.filter(session=session, state__in=[
        VoiceTurn.State.TRANSCRIBING, VoiceTurn.State.TRANSCRIBED,
        VoiceTurn.State.PROCESSING, VoiceTurn.State.ANSWER_SAVED, VoiceTurn.State.SYNTHESIZING,
    ]).exclude(request_id=_uuid(request_id)).exists():
        raise VoiceConflict("Another voice turn is already processing.")
    turn, _ = prepare_voice_turn(user=user, session_id=session_id, request_id=request_id, audio=audio)
    # A persistent compare-and-swap claim survives crashes and lost responses.
    claimed = VoiceTurn.objects.filter(pk=turn.pk, state=VoiceTurn.State.CREATED).update(
        state=VoiceTurn.State.TRANSCRIBING, updated_at=timezone.now(),
    ) == 1
    turn.refresh_from_db()
    return turn, claimed


def result_for(turn):
    return {
        "state": turn.state,
        "transcript": turn.transcript,
        "has_assistant_answer": turn.assistant_message_id is not None,
        "audio_available": bool(turn.state == VoiceTurn.State.COMPLETED and turn.output_audio_key),
    }


def execute_voice_chain(*, user, session_id, request_id, audio):
    providers = configured_providers()
    turn, claimed = claim_transcription(user=user, session_id=session_id, request_id=request_id, audio=audio)
    if not claimed:
        # Status/audio recovery only: never repeat a previously claimed stage.
        return result_for(turn)
    try:
        guard(user, session_id)
        transcript = providers.transcribe(audio)
        guard(user, session_id)
        save_transcript(user=user, session_id=session_id, request_id=turn.request_id, transcript=transcript)
        guard(user, session_id)
        # Existing engine owns prompt, personality, KB, history and atomic saving.
        # No alternative assistant or message-persistence path is introduced.
        with mock_ai_provider(providers.mock_ai):
            process_voice_answer(user=user, session_id=session_id, request_id=turn.request_id)
        guard(user, session_id)
        turn, claimed_tts = claim_tts_dispatch(user=user, session_id=session_id, request_id=turn.request_id)
        if not claimed_tts:
            return result_for(turn)
        message = turn.assistant_message
        session = turn.session
        if (message.user_id != user.pk or message.bot_id != session.assistant_id
                or message.conversation_id != session.conversation_id):
            raise VoiceAccessDenied("Saved answer identity mismatch.")
        text = message.message
        guard(user, session_id)
        output = validate_live_mp3(providers.synthesize(text))
        guard(user, session_id)
        key = uuid4()
        store = LocalVoiceAudioStore(user_id=user.pk)
        store.save(request_id=key, audio=output)
        try:
            with transaction.atomic():
                guard(user, session_id)
                # Lock against simultaneous stop and verify the saved answer.
                locked_session = _session(user, session_id, lock=True)
                locked = VoiceTurn.objects.select_for_update().get(pk=turn.pk, session=locked_session)
                if locked.state != VoiceTurn.State.SYNTHESIZING or locked.assistant_message.message != text:
                    raise VoiceConflict("Saved answer changed during synthesis.")
                locked.output_audio_key = key
                locked.output_audio_sha256 = sha256(output).hexdigest()
                locked.state = VoiceTurn.State.COMPLETED
                locked.save(update_fields=["output_audio_key", "output_audio_sha256", "state", "updated_at"])
                turn = locked
        except Exception:
            # The private store already bounds retention by TTL; an unpublished
            # orphan is never exposed and is not grounds to synthesize again.
            raise
        return result_for(turn)
    except Exception as exc:
        logger.warning("U6.3 voice processing stopped for turn %s", turn.pk, exc_info=True)
        # Record the uncertain outcome without requiring a still-active session.
        # Saved transcript/messages survive expiry, revocation and provider errors.
        code = "session_unavailable" if isinstance(exc, VoiceAccessDenied) else "voice_processing_uncertain"
        VoiceTurn.objects.filter(pk=turn.pk, state__in=[
            VoiceTurn.State.TRANSCRIBING, VoiceTurn.State.TRANSCRIBED,
            VoiceTurn.State.PROCESSING, VoiceTurn.State.ANSWER_SAVED, VoiceTurn.State.SYNTHESIZING,
        ]).update(state=VoiceTurn.State.UNCERTAIN, error_code=code, updated_at=timezone.now())
        if isinstance(exc, VoiceAccessDenied):
            raise
        turn.refresh_from_db()
        return result_for(turn)


def retrieve_chain_audio(*, user, session_id, turn):
    guard(user, session_id)
    if turn.state != VoiceTurn.State.COMPLETED or not turn.output_audio_key:
        return None
    audio = LocalVoiceAudioStore(user_id=user.pk).load(request_id=turn.output_audio_key)
    if audio is None or sha256(audio).hexdigest() != turn.output_audio_sha256:
        return None
    guard(user, session_id)
    return validate_live_mp3(audio)
