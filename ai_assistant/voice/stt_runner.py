"""Internal U6.3 bridge to U6.1 STT.

This is not an HTTP endpoint. The caller must supply:
- validated U6.1 Audio
- a persisted matching reservation
- server-verified subscription evidence

Provider execution is deliberately disabled until integration tests
and a trusted entitlement verifier have been completed.
"""

from ai_assistant.stt.normalizer import ServerPeriodEvidence

from .models import VoiceTurn
from .service import (
    VoiceAccessDenied,
    VoiceConflict,
    _session,
    _uuid,
)
from .stt_entitlement import validate_voice_evidence


def prepare_reserved_stt(
    *,
    user,
    session_id,
    request_id,
    reservation,
    evidence,
    audio,
):
    """Validate all identities without dispatching or changing quotas."""

    session = _session(user, session_id)

    turn = VoiceTurn.objects.filter(
        session=session,
        request_id=_uuid(request_id),
    ).first()

    if turn is None:
        raise VoiceAccessDenied("Voice turn not found.")

    if turn.state != VoiceTurn.State.CREATED:
        raise VoiceConflict("STT turn already started.")

    if not isinstance(evidence, ServerPeriodEvidence):
        raise VoiceAccessDenied("Verified evidence required.")

    validate_voice_evidence(user=user, evidence=evidence)

    if (
        str(reservation.request_id) != str(turn.request_id)
        or reservation.audio_sha256 != turn.audio_sha256
        or reservation.assistant_id != session.assistant_id
        or reservation.account.user_id != user.pk
    ):
        raise VoiceConflict("STT reservation mismatch.")

    if getattr(audio, "sha256", None) != turn.audio_sha256:
        raise VoiceConflict("Audio fingerprint mismatch.")

    return session, turn


def execute_reserved_stt(
    *,
    user,
    session_id,
    request_id,
    reservation,
    evidence,
    audio,
    api_key,
):
    """Fail closed until provider execution has been fully verified."""

    prepare_reserved_stt(
        user=user,
        session_id=session_id,
        request_id=request_id,
        reservation=reservation,
        evidence=evidence,
        audio=audio,
    )

    raise VoiceConflict(
        "STT provider dispatch is not enabled yet."
    )
