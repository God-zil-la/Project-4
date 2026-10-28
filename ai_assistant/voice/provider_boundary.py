"""Transparent billing bridge with an opt-in U6.3 voice dispatch guard."""
from ai_assistant.accounts.campaign import provider_call as _campaign_provider_call
from .provider_guard import has_voice_scope, check_provider_allowed, dispatch_provider


def provider_call(create, *, campaign_user=None, **kwargs):
    if not has_voice_scope():
        # Preserve the original callable, kwargs, errors and billing semantics.
        return _campaign_provider_call(create, campaign_user=campaign_user, **kwargs)
    # Do not reserve any provider billing allowance for an already invalid turn.
    check_provider_allowed()

    def guarded_create(**provider_kwargs):
        # A billing reservation or other pre-dispatch work may take time.
        # Re-read server state at the actual invocation, not just at stage entry.
        check_provider_allowed()
        return dispatch_provider(create, provider_kwargs)

    return _campaign_provider_call(guarded_create, campaign_user=campaign_user, **kwargs)
