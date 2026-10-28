"""Authorized access to privately stored U6.2 audio."""

from .audio_access import authorize_audio_request


def retrieve_audio(*, user, assistant_id, request_id, store):
    row = authorize_audio_request(
        user=user,
        assistant_id=assistant_id,
        request_id=request_id,
    )

    if row.state != "succeeded":
        return None

    audio = store.load(request_id=row.pk)
    if audio is None:
        return None

    # Recheck authorization after accessing storage.
    current = authorize_audio_request(
        user=user,
        assistant_id=assistant_id,
        request_id=request_id,
    )

    if current.pk != row.pk or current.state != "succeeded":
        return None

    return audio
