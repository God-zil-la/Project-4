"""Coordinate saved-response synthesis with private audio storage.

Backend-only integration. No production provider or public endpoint.
"""

from .audio_finalization import finalize_stored_audio


def store_synthesized_audio(*, user_id, row_id, request_id, audio, store):
    """Finalize a dispatched request only after audio is stored."""
    return finalize_stored_audio(
        user_id=user_id,
        row_id=row_id,
        request_id=request_id,
        audio=audio,
        store=store,
    )
