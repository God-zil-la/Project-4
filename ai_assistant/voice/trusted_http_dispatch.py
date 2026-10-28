"""U6.3 trusted HTTP-to-live-voice dispatch bridge.

This module is server-internal.

It never reads subscription evidence, reservations, transcribers,
or provider credentials from client input.

No public endpoint or automatic provider activation.
"""
from django.db import transaction

from dataclasses import dataclass
from typing import Callable

from ai_assistant.stt.normalizer import ServerPeriodEvidence

from .service import VoiceConflict
from .turn_prepare import prepare_voice_turn
from .trusted_live_integration import execute_trusted_live_voice
from .stt_entitlement import validate_voice_evidence


@dataclass(frozen=True)
class TrustedVoiceDependencies:
    """Dependencies supplied by verified server-side integration."""

    resolve_evidence: Callable
    reserve_stt: Callable
    transcribe: Callable
    audio_store: object = None
    synthesize: object = None


def dispatch_trusted_http_voice(
    *,
    user,
    session_id,
    request_id,
    audio,
    dependencies,
):
    """Prepare and execute one trusted voice turn.

    The HTTP layer must authenticate the user, enforce ownership,
    and validate the WAV before invoking this function.

    The dependency provider must be trusted server-side code.
    """

    if not isinstance(dependencies, TrustedVoiceDependencies):
        raise VoiceConflict(
            "Trusted server dependencies required."
        )

    if not callable(dependencies.resolve_evidence):
        raise VoiceConflict(
            "Trusted entitlement resolver required."
        )

    if not callable(dependencies.reserve_stt):
        raise VoiceConflict(
            "Trusted STT reservation function required."
        )

    if not callable(dependencies.transcribe):
        raise VoiceConflict(
            "Trusted transcriber required."
        )

    if (
        dependencies.synthesize is not None
        and not callable(dependencies.synthesize)
    ):
        raise VoiceConflict(
            "Invalid TTS synthesizer."
        )

    # Resolve entitlement before creating a voice turn.
    evidence = dependencies.resolve_evidence(user=user)
    validate_voice_evidence(user=user, evidence=evidence)

    if not isinstance(evidence, ServerPeriodEvidence):
        raise VoiceConflict(
            "Verified subscription evidence required."
        )

    # Persist idempotent voice-turn identity.
    with transaction.atomic():
        turn, created = prepare_voice_turn(
            user=user,
            session_id=session_id,
            request_id=request_id,
            audio=audio,
        )

        if not created:
            raise VoiceConflict(
                "Voice request already exists; refusing redispatch."
            )

        # Reservation is always supplied by trusted server-side code.
        # Do not accept subscription or reservation details from HTTP input.
        reservation = dependencies.reserve_stt(
            evidence=evidence,
            request_id=turn.request_id,
            duration_ms=audio.milliseconds,
            audio_sha256=audio.sha256,
            assistant_id=turn.session.assistant_id,
        )

    if reservation is None:
        raise VoiceConflict(
            "STT reservation was not created."
        )

    return execute_trusted_live_voice(
        user=user,
        session_id=session_id,
        request_id=turn.request_id,
        reservation=reservation,
        evidence=evidence,
        audio=audio,
        transcriber=dependencies.transcribe,
        audio_store=dependencies.audio_store,
        real_tts_synthesize=dependencies.synthesize,
    )

def serialize_voice_dispatch_result(result):
    """Serialize safe U6.3 voice metadata without exposing raw audio."""

    if not isinstance(result, dict):
        return {}

    voice = result.get("voice")
    if not isinstance(voice, dict):
        voice = {}

    output = {}

    state = voice.get("state")
    if isinstance(state, str):
        output["state"] = state

    transcript = result.get("transcript")
    if isinstance(transcript, str):
        output["transcript"] = transcript

    stt_state = result.get("stt_state")
    if isinstance(stt_state, str):
        output["stt_state"] = stt_state

    audio_available = voice.get("audio_available")
    if type(audio_available) is bool:
        output["audio_available"] = audio_available

    return output