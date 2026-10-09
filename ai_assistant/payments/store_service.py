"""Store ownership, serialization and access policy shared by API and notifications."""
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from ai_assistant.accounts.models import UserProfile
from .models import (CheckoutAttempt, StoreIdentity, StorePurchaseIntent, StoreSubscription,
                     SubscriptionChange, SubscriptionRecovery)
from .store_config import PRODUCTS, StoreError, config, configured, environment
from . import store_verification as verification

ACCESS_STATES = ('active', 'grace', 'canceled')
ENDED_STATES = ('expired', 'revoked', 'replaced')


def valid_subscriptions(profile):
    return StoreSubscription.objects.filter(identity__profile=profile,
        state__in=ACCESS_STATES, expires_at__gt=timezone.now()).filter(
            Q(provider='apple', environment=config('APPLE_ENVIRONMENT')) |
            Q(provider='google', environment=config('GOOGLE_ENVIRONMENT')))


def store_plan(profile):
    plans = set(valid_subscriptions(profile).values_list('plan', flat=True))
    return 'pro' if 'pro' in plans else 'premium' if 'premium' in plans else 'free'


def store_blocks_checkout(profile):
    return (StorePurchaseIntent.objects.filter(profile=profile).exists()
            or StoreSubscription.objects.filter(identity__profile=profile).exclude(state__in=ENDED_STATES).exists())


def purchase_block(profile):
    from .state import has_existing_subscription
    if has_existing_subscription(profile) or profile.subscription_plan != 'free':
        return 'Manage your existing website subscription to avoid a second subscription.'
    if CheckoutAttempt.objects.filter(profile=profile).exists():
        return 'Resolve the existing website checkout before purchasing in the app.'
    if SubscriptionRecovery.objects.filter(profile=profile, completed=False).exists() or (
        SubscriptionChange.objects.filter(profile=profile).exclude(status__in=['complete', 'removed', 'failed']).exists()
    ):
        return 'Resolve the pending website billing change first.'
    if StoreSubscription.objects.filter(identity__profile=profile).exclude(state__in=ENDED_STATES).exists():
        return 'Manage or restore your existing store subscription before starting another.'
    if profile.has_complimentary_access:
        return 'This account already has complimentary access. No purchase is needed.'
    return ''


def identity_for(profile):
    return StoreIdentity.objects.get_or_create(profile=profile)[0]


def reconcile_web_checkout(profile):
    """Legacy/open Stripe sessions also block native checkout, even without an intent."""
    import stripe
    from django.conf import settings
    sessions = list(stripe.checkout.Session.list(customer=profile.stripe_customer_id,
        limit=100, api_key=settings.STRIPE_SECRET_KEY).auto_paging_iter())
    for session in sessions:
        if session.get('customer') != profile.stripe_customer_id:
            raise StoreError('Website billing needs reconciliation.', 409)
        if session.get('mode') == 'subscription' and session.get('status') not in {'complete', 'expired'}:
            raise StoreError('An existing website checkout is still open. Resolve it before purchasing here.', 409)
    attempt = CheckoutAttempt.objects.filter(profile=profile).first()
    if attempt and attempt.session_id:
        known = next((s for s in sessions if s.get('id') == attempt.session_id), None)
        if known and known.get('status') in {'complete', 'expired'}:
            # Stripe subscription inventory was already refreshed under this same lock.
            attempt.delete()


@transaction.atomic
def start_purchase(user, provider, product):
    from .state import reconcile_customer
    if provider not in {'apple', 'google'} or product not in PRODUCTS.values():
        raise StoreError('Invalid store or product.', 400)
    if not configured(provider):
        raise StoreError('Purchases are not available yet. Please try again later.')
    environment(provider)
    profile = UserProfile.objects.select_for_update().get(user=user)
    # Refresh existing Stripe inventory before authorizing a native payment.
    if profile.stripe_customer_id:
        reconcile_customer(profile)
        reconcile_web_checkout(profile)
    reason = purchase_block(profile)
    if reason:
        raise StoreError(reason, 409)
    intent, _ = StorePurchaseIntent.objects.get_or_create(profile=profile,
        defaults={'provider': provider, 'product_id': product})
    if intent.provider != provider or intent.product_id != product:
        raise StoreError('A purchase is awaiting confirmation. Restore purchases before choosing another plan.', 409)
    return identity_for(profile)


def apply_verified(profile, verified):
    """Caller holds the profile lock; reference uniqueness enforces one owner."""
    identity = identity_for(profile)
    if verified.owner != str(identity.token):
        raise StoreError('This purchase belongs to a different AI Assistant account. Sign in to the original account.', 409)
    row, _ = StoreSubscription.objects.get_or_create(provider=verified.provider,
        environment=verified.environment, reference=verified.reference,
        defaults={'identity': identity, 'plan': verified.plan, 'product_id': verified.product_id,
                  'state': verified.state})
    if row.identity_id != identity.pk:
        raise StoreError('This purchase is already linked to another account.', 409)
    if row.state == 'replaced':
        return row
    if verified.linked_reference:
        previous = StoreSubscription.objects.filter(provider='google', environment=verified.environment,
                                                     reference=verified.linked_reference).first()
        if previous and previous.identity_id != identity.pk:
            raise StoreError('The previous purchase belongs to another account.', 409)
        if previous:
            previous.state = 'replaced'
            previous.save(update_fields=['state'])
    for field in ('product_id', 'base_plan_id', 'plan', 'state', 'expires_at', 'auto_renew'):
        setattr(row, field, getattr(verified, field))
    if verified.purchase_token:
        row.encrypted_token = verification.encrypt_token(verified.purchase_token)
    row.verified_at = timezone.now()
    row.save()
    if verified.state != 'pending':
        StorePurchaseIntent.objects.filter(profile=profile, provider=verified.provider,
                                           product_id=verified.product_id).delete()
    return row


def verify_purchase(user, provider, reference):
    if provider not in {'apple', 'google'} or not isinstance(reference, str) or not 1 <= len(reference) <= 4096:
        raise StoreError('Invalid purchase reference.', 400)
    if not configured(provider):
        raise StoreError()
    with transaction.atomic():
        profile = UserProfile.objects.select_for_update().get(user=user)
        verified = verification.verify_apple(reference) if provider == 'apple' else verification.verify_google(reference)
        apply_verified(profile, verified)
    # Acknowledgement happens only after commit; failure is retryable without losing access.
    if provider == 'google':
        verification.acknowledge_google(verified)
    return verified


def refresh_subscriptions(user):
    # Iterate stable references, then serialize each authoritative fetch with all writers.
    rows = list(StoreSubscription.objects.filter(identity__profile__user=user).exclude(state='replaced'))
    for row in rows:
        ref = row.reference if row.provider == 'apple' else verification.decrypt_token(row.encrypted_token)
        verify_purchase(user, row.provider, ref)


def status_for(profile):
    rows = StoreSubscription.objects.filter(identity__profile=profile)
    reason = purchase_block(profile)
    intent = StorePurchaseIntent.objects.filter(profile=profile).first()
    return {'effective_plan': profile.effective_plan, 'purchase_block': reason,
        'pending_intent': {'provider': intent.provider, 'product_id': intent.product_id} if intent else None,
        'stripe_managed': bool(profile.stripe_customer_id or profile.stripe_subscription_id),
        'subscriptions': [{'provider': row.provider, 'product_id': row.product_id,
            'plan': row.plan, 'state': row.state, 'expires_at': row.expires_at,
            'auto_renew': row.auto_renew} for row in rows]}
