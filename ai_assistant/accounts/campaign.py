"""K1 entitlement and conservative, atomic provider token reservations."""
from contextvars import ContextVar
from datetime import timedelta
from functools import wraps
import hmac
import json

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import UserProfile

TOKEN_LIMIT = 2_000_000
_account = ContextVar('k1_account', default=None)


def redeem(user, code):
    expected = getattr(settings, 'K1_CAMPAIGN_CODE', '')
    if not getattr(settings, 'K1_CAMPAIGN_ENABLED', False) or not expected:
        raise ValueError('This campaign is not available.')
    if not hmac.compare_digest(str(code).encode(), expected.encode()):
        raise ValueError('Invalid campaign code.')
    with transaction.atomic():
        profile = UserProfile.objects.select_for_update().get(user=user)
        if not user.is_active or profile.effective_plan != UserProfile.PLAN_FREE:
            raise ValueError('This campaign is available to active Free accounts only.')
        now = timezone.now()
        updated = UserProfile.objects.filter(
            pk=profile.pk, campaign_started_at__isnull=True,
        ).update(campaign_started_at=now, campaign_ends_at=now + timedelta(days=14))
        if not updated:
            raise ValueError('This account has already redeemed the campaign.')


def campaign_scope(function):
    """All nested AI calls inherit the billed account, including auxiliary calls."""
    @wraps(function)
    def wrapped(user, *args, **kwargs):
        profile = user.profile
        if isinstance(profile, UserProfile):
            profile.refresh_from_db()
        token = _account.set(profile.pk if profile.has_campaign_access is True else None)
        try:
            return function(user, *args, **kwargs)
        finally:
            _account.reset(token)
    return wrapped


def provider_call(create, *, campaign_user=None, **kwargs):
    """Reserve an upper bound before sending; refund only confirmed unused tokens.

    UTF-8 bytes bound text BPE tokens; JSON plus per-message padding bounds
    framing for the fixed text-only models. Unknown models/features fail closed.
    Timeouts/missing usage retain the reservation, since they may be billable.
    """
    account = _account.get()
    if campaign_user is not None:
        profile = UserProfile.objects.get(user_id=campaign_user.pk)
        account = profile.pk if profile.has_campaign_access is True else None
    if account is None:
        return create(**kwargs)
    model = kwargs.get('model')
    if model not in {'gpt-4o-mini', 'text-embedding-3-small'}:
        raise ValueError('Model is not supported by this campaign.')
    if kwargs.get('stream') or kwargs.get('tools') or kwargs.get('n', 1) != 1:
        raise ValueError('Unsupported campaign request.')
    payload = kwargs.get('messages', kwargs.get('input'))
    if model == 'gpt-4o-mini' and not isinstance(kwargs.get('max_tokens'), int):
        raise ValueError('Campaign requests require a bounded output.')
    reserved = len(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
    reserved += 256 + 32 * (len(payload) if isinstance(payload, list) else 1)
    reserved += kwargs.get('max_tokens', 0)
    now = timezone.now()
    if not UserProfile.objects.filter(
        pk=account, campaign_ends_at__gt=now,
        campaign_tokens__lte=TOKEN_LIMIT - reserved - F("campaign_reserved_tokens"),
    ).update(campaign_reserved_tokens=F('campaign_reserved_tokens') + reserved):
        from ai_assistant.bots.chat_service import ChatUsageLimitError
        raise ChatUsageLimitError('Campaign token allowance is insufficient or expired.', {
            'allowed': False, 'plan': 'pro', 'monthly_message_limit_reached': False,
            'monthly_cost_limit_reached': False,
        })
    # Persist a conservative charge even when the provider fails or omits usage.
    actual = reserved
    try:
        response = create(**kwargs)
        usage = response.get('usage') or {}
        input_tokens = usage.get('prompt_tokens')
        output_tokens = usage.get('completion_tokens', 0 if model == 'text-embedding-3-small' else None)
        if all(type(value) is int and value >= 0 for value in (input_tokens, output_tokens)):
            measured = input_tokens + output_tokens
            if measured <= reserved:
                actual = measured
        return response
    finally:
        UserProfile.objects.filter(pk=account).update(
            campaign_reserved_tokens=F('campaign_reserved_tokens') - reserved,
            campaign_tokens=F('campaign_tokens') + actual,
        )
