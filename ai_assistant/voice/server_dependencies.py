"""Server-only dependency construction for U6.3 Live Voice.

No HTTP request body, headers, query parameters or client-provided
credentials may configure these dependencies.

Constructing dependencies does not invoke STT, AI or TTS providers.
"""

from dataclasses import dataclass
from typing import Callable

from .real_stt_provider import make_real_stt_transcriber
from .service import VoiceConflict
from .trusted_http_dispatch import TrustedVoiceDependencies


@dataclass(frozen=True)
class TrustedServerConfiguration:
    """Server-owned callbacks for verified voice execution."""

    resolve_evidence: Callable
    reserve_stt: Callable
    audio_store: object = None
    synthesize: object = None


def build_server_voice_dependencies(
    *,
    configuration,
    allow_paid_calls=False,
):
    """Construct trusted dependencies without dispatching providers.

    Both explicit permission and the server environment gate are
    required before the real STT transcriber can be constructed.
    """

    if not isinstance(configuration, TrustedServerConfiguration):
        raise VoiceConflict(
            "Voice dependencies require trusted server configuration."
        )

    if not callable(configuration.resolve_evidence):
        raise VoiceConflict(
            "Server subscription evidence resolver is unavailable."
        )

    if not callable(configuration.reserve_stt):
        raise VoiceConflict(
            "Server STT reservation callback is unavailable."
        )

    if configuration.synthesize is not None:
        if not callable(configuration.synthesize):
            raise VoiceConflict(
                "Server TTS callback is invalid."
            )

    if configuration.audio_store is not None:
        if not (
            callable(getattr(configuration.audio_store, "save", None))
            and callable(getattr(configuration.audio_store, "load", None))
        ):
            raise VoiceConflict(
                "Server audio storage interface is invalid."
            )

    # This fails closed unless the caller explicitly authorizes
    # paid calls AND U63_REAL_STT_ENABLED=true is set server-side.
    #
    # No provider request occurs during construction.
    transcriber = make_real_stt_transcriber(
        allow_paid_calls=allow_paid_calls
    )

    return TrustedVoiceDependencies(
        resolve_evidence=configuration.resolve_evidence,
        reserve_stt=configuration.reserve_stt,
        transcribe=transcriber,
        audio_store=configuration.audio_store,
        synthesize=configuration.synthesize,
    )


_server_voice_dependencies = None


def install_server_voice_dependencies(dependencies):
    """Install verified server-owned voice dependencies."""
    global _server_voice_dependencies

    if not isinstance(dependencies, TrustedVoiceDependencies):
        raise VoiceConflict(
            "Invalid server voice dependency configuration."
        )

    _server_voice_dependencies = dependencies


def get_disabled_server_voice_dependencies():
    """Return installed dependencies; disabled by default."""
    return _server_voice_dependencies


def resolve_http_voice_dependencies(*, request):
    """Return only explicitly installed server-owned dependencies.

    This function does not read request data, headers, query
    parameters, cookies or client-provided configuration.

    The default remains disabled.
    """
    dependencies = get_disabled_server_voice_dependencies()

    if dependencies is None:
        dependencies = resolve_local_http_voice_dependencies(request=request)

    if dependencies is None:
        return None

    if not isinstance(dependencies, TrustedVoiceDependencies):
        raise VoiceConflict(
            "Invalid server voice dependency configuration."
        )

    return dependencies



def resolve_local_http_voice_dependencies(*, request=None):
    import os
    from django.conf import settings

    if not getattr(settings, "U63_EXTERNAL_PROVIDER_APPROVAL", False):
        return None

    if os.environ.get("U63_LOCAL_LIVE_VOICE_ENABLED") != "true":
        return None

    if not settings.DEBUG or request is None:
        return None

    user = getattr(request, "user", None)

    if user is None or not user.is_authenticated:
        return None

    from .local_live_voice import build_local_live_voice_dependencies

    return build_local_live_voice_dependencies(user=user, allow_paid_calls=True)
