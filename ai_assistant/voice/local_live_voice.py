"""U6.3 local Live Voice dependencies.

Explicitly enabled development configuration only.
"""

from django.conf import settings

from ai_assistant.stt.normalizer import reserve_normalized

from .local_audio_store import LocalVoiceAudioStore
from .real_tts_provider import synthesize_live_voice_audio
from .server_dependencies import (
    TrustedServerConfiguration,
    build_server_voice_dependencies,
)
from .stripe_evidence import resolve_stripe_voice_evidence


def build_local_live_voice_dependencies(*, user=None, allow_paid_calls=False):
    if allow_paid_calls is not True or not getattr(settings, "U63_EXTERNAL_PROVIDER_APPROVAL", False):
        raise RuntimeError("u63_external_provider_approval_required")
    if not settings.DEBUG:
        raise RuntimeError("local_voice_requires_debug")

    if user is None or not user.is_authenticated:
        raise RuntimeError("authenticated_user_required")

    store = LocalVoiceAudioStore(user_id=user.pk)

    configuration = TrustedServerConfiguration(
        resolve_evidence=resolve_stripe_voice_evidence,
        reserve_stt=reserve_normalized,
        audio_store=store,
        synthesize=lambda *, text: synthesize_live_voice_audio(
            text=text,
            allow_paid_calls=allow_paid_calls,
        ),
    )

    return build_server_voice_dependencies(
        configuration=configuration,
        allow_paid_calls=allow_paid_calls,
    )
