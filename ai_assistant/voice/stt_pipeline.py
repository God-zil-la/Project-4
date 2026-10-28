"""U6.3 internal STT pipeline.

No external provider is imported or called here.
The transcription function must be injected by trusted server code.
"""

from dataclasses import dataclass

from django.db import transaction

from ai_assistant.stt import ledger
from ai_assistant.stt.normalizer import ServerPeriodEvidence

from .models import VoiceTurn
from .service import (
    VoiceConflict,
    advance_turn,
)
from .stt_entitlement import claim_voice_stt
from .stt_runner import prepare_reserved_stt
from .stt_adapter import accept_stt_result


@dataclass(frozen=True)
class STTPipelineResult:
    state: str
    transcript: str = ""


def execute_testable_stt(
    *,
    user,
    session_id,
    request_id,
    reservation,
    evidence,
    audio,
    transcriber,
):
    """Execute a reserved STT turn using an injected provider.

    Must only be invoked by trusted server code. The caller is
    responsible for supplying a server-verified subscription period.
    """

    if not callable(transcriber):
        raise VoiceConflict("Trusted transcriber required.")

    if not isinstance(evidence, ServerPeriodEvidence):
        raise VoiceConflict("Verified entitlement required.")

    session, turn = prepare_reserved_stt(
        user=user,
        session_id=session_id,
        request_id=request_id,
        reservation=reservation,
        evidence=evidence,
        audio=audio,
    )

    # Persistent at-most-once claim. Never automatically retry a
    # dispatched request after a crash or uncertain provider outcome.
    # U6.1 owns the durable dispatch transaction. Never nest it
    # inside another atomic block or roll back a successful claim.
    claimed = claim_voice_stt(
        user=user,
        evidence=evidence,
        reservation_id=reservation.pk,
    )

    if not claimed:
        raise VoiceConflict("STT already dispatched.")

    # A failed state transition must prevent provider invocation.
    # The dispatched reservation remains held for reconciliation.
    advance_turn(
        user=user,
        session_id=session.public_id,
        request_id=turn.request_id,
        expected=VoiceTurn.State.CREATED,
        target=VoiceTurn.State.TRANSCRIBING,
    )

    # No transaction is held open during an external provider call.
    try:
        from .service import _session
        _session(user, session_id)
        transcript = transcriber(audio)
    except Exception:
        # The provider might have received the request.
        # Do not release the quota as definitively unprocessed.
        ledger.settle(
            user_id=user.pk,
            reservation_id=reservation.pk,
            outcome="uncertain",
        )
        advance_turn(
            user=user,
            session_id=session.public_id,
            request_id=turn.request_id,
            expected=VoiceTurn.State.TRANSCRIBING,
            target=VoiceTurn.State.UNCERTAIN,
        )
        raise

    if not isinstance(transcript, str) or not transcript.strip():
        ledger.settle(
            user_id=user.pk,
            reservation_id=reservation.pk,
            outcome="uncertain",
        )
        advance_turn(
            user=user,
            session_id=session.public_id,
            request_id=turn.request_id,
            expected=VoiceTurn.State.TRANSCRIBING,
            target=VoiceTurn.State.UNCERTAIN,
        )
        raise VoiceConflict("Empty or invalid transcription.")

    # Charge only for a successful response.
    ledger.settle(
        user_id=user.pk,
        reservation_id=reservation.pk,
        outcome="success",
    )

    accept_stt_result(
        user=user,
        session_id=session.public_id,
        request_id=turn.request_id,
        reservation_id=reservation.pk,
        transcript=transcript,
    )

    return STTPipelineResult(
        state=VoiceTurn.State.TRANSCRIBED,
        transcript=transcript.strip(),
    )
