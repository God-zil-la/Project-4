"""U6.3 internal voice-turn preparation.

No STT reservation, provider dispatch or quota changes.
"""

import re

from .service import VoiceAccessDenied, reserve_turn


def prepare_voice_turn(*, user, session_id, request_id, audio):
    fingerprint = getattr(audio, "sha256", None)
    duration = getattr(audio, "milliseconds", None)

    if not isinstance(fingerprint, str) or not re.fullmatch(
        r"[0-9a-f]{64}", fingerprint
    ):
        raise VoiceAccessDenied("Invalid audio fingerprint.")

    if (
        isinstance(duration, bool)
        or not isinstance(duration, int)
        or duration <= 0
        or duration > 300000
    ):
        raise VoiceAccessDenied("Invalid audio duration.")

    turn, created = reserve_turn(
        user=user,
        session_id=session_id,
        request_id=request_id,
        audio_sha256=fingerprint,
    )

    return turn, created
