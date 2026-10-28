"""U6.3 authenticated audio retrieval bridge."""

import os

from django.conf import settings

from ai_assistant.tts.audio_retrieval import retrieve_audio

from .local_audio_store import LocalVoiceAudioStore


def build_voice_audio_store(*, user):
    if (
        settings.DEBUG
        and os.environ.get("U63_LOCAL_LIVE_VOICE_ENABLED") == "true"
    ):
        return LocalVoiceAudioStore(user_id=user.pk)

    if not (
        getattr(settings, "U62_CLEANUP_ENABLED", False)
        and getattr(settings, "U62_R2_ENABLED", False)
    ):
        return None

    from ai_assistant.tts.cleanup_dependencies import (
        build_cleanup_dependencies,
    )
    from ai_assistant.tts.durable_audio_store import (
        DurableR2AudioStore,
    )

    repository, r2_store = build_cleanup_dependencies()

    return DurableR2AudioStore(
        repository=repository,
        r2_store=r2_store,
        user_id=user.pk,
    )


def retrieve_voice_audio(*, user, assistant_id, voice_request_id):
    store = build_voice_audio_store(user=user)

    if store is None:
        return None

    return retrieve_audio(
        user=user,
        assistant_id=assistant_id,
        request_id=voice_request_id,
        store=store,
    )
