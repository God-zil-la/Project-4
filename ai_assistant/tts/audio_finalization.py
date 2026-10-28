"""Save generated audio before marking a TTS request as succeeded."""

from . import service
from .audio_storage import validate_audio


def finalize_stored_audio(*, user_id, row_id, request_id, audio, store):
    """Persist audio first; never report success when storage fails."""
    validate_audio(audio)

    try:
        store.save(request_id=row_id, audio=audio)
    except Exception:
        service.finish(user_id=user_id, row_id=row_id, state="uncertain")
        raise

    # Retain private bytes until TTL if the database commit fails. An explicit
    # authorized recovery can finalize them without synthesizing again.
    return service.finish(user_id=user_id, row_id=row_id, state="succeeded")
