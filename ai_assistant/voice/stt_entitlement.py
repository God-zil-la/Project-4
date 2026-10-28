"""Trusted U6.3 bridge to the U6.1 subscription-period normalizer.

Do not expose evidence as a client-controlled API parameter.
The server-side payment verification integration must supply it.
"""

from ai_assistant.stt.normalizer import (
    ServerPeriodEvidence,
    normalize,
    reserve_normalized,
    claim_normalized,
)

from .service import VoiceAccessDenied


def validate_voice_evidence(*, user, evidence):
    if not isinstance(evidence, ServerPeriodEvidence):
        raise VoiceAccessDenied("Verified server evidence required.")

    if evidence.user_id != user.pk:
        raise VoiceAccessDenied("Subscription owner mismatch.")

    verified_period = normalize(evidence)

    if verified_period.user_id != user.pk:
        raise VoiceAccessDenied("Verified period owner mismatch.")

    return verified_period


def reserve_voice_stt(
    *,
    user,
    evidence,
    request_id,
    duration_ms,
    audio_sha256,
    assistant_id,
):
    validate_voice_evidence(
        user=user,
        evidence=evidence,
    )

    return reserve_normalized(
        evidence=evidence,
        request_id=request_id,
        duration_ms=duration_ms,
        audio_sha256=audio_sha256,
        assistant_id=assistant_id,
    )


def claim_voice_stt(*, user, evidence, reservation_id):
    validate_voice_evidence(
        user=user,
        evidence=evidence,
    )

    return claim_normalized(
        evidence=evidence,
        reservation_id=reservation_id,
    )
