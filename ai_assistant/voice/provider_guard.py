"""Context-local U6.3 authorization checked at each internal AI dispatch."""
from contextlib import contextmanager
from contextvars import ContextVar

_voice_scope = ContextVar("u63_provider_deadline_scope", default=None)


@contextmanager
def voice_provider_scope(*, user, session_id, request_id):
    token = _voice_scope.set((user.pk, session_id, request_id))
    try:
        yield
    finally:
        _voice_scope.reset(token)


def has_voice_scope():
    return _voice_scope.get() is not None


def check_provider_allowed():
    scope = _voice_scope.get()
    if scope is None:
        return
    # Imports and database reads occur only in a voice request. A text request
    # neither depends on voice tables nor reconstructs any quota/billing policy.
    from django.contrib.auth import get_user_model
    from .models import VoiceTurn
    from .service import VoiceAccessDenied, _session, _uuid
    from .live_free_entitlement import require_free_voice_access

    user_id, session_id, request_id = scope
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        raise VoiceAccessDenied("Voice account is no longer active.")
    session = _session(user, session_id)
    if not session.deadline_at or not session.quota_reservation_id:
        raise VoiceAccessDenied("Reserved voice deadline required.")
    require_free_voice_access(user=user)
    reservation = session.quota_reservation
    if (reservation.state != "reserved" or reservation.user_id != user.pk
            or reservation.usage.user_id != user.pk):
        raise VoiceAccessDenied("Voice reservation is no longer active.")
    if not VoiceTurn.objects.filter(
        session=session, request_id=_uuid(request_id),
        state=VoiceTurn.State.PROCESSING, assistant_message_id__isnull=True,
    ).exists():
        raise VoiceAccessDenied("Voice provider dispatch is no longer valid.")
    # Identity/entitlement reads can themselves take time. This is the final
    # operation before returning to guarded_create and invoking the provider.
    from django.utils import timezone
    if timezone.now() >= session.deadline_at:
        raise VoiceAccessDenied("Voice session expired before provider dispatch.")


_mock_ai = ContextVar("u63_local_mock_ai", default=None)


@contextmanager
def mock_ai_provider(callback):
    if not callable(callback):
        raise ValueError("Explicit local mock AI callback required.")
    token = _mock_ai.set(callback)
    try:
        yield
    finally:
        _mock_ai.reset(token)


def dispatch_provider(create, kwargs):
    callback = _mock_ai.get()
    if callback is not None:
        # Do not hand the real provider function to a mock transport. There is
        # no implicit fallback to OpenAI if a local mock is missing a response.
        return callback(**kwargs)
    return create(**kwargs)
