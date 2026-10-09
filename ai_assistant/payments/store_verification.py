"""Authoritative store adapters. Never trust client price, plan, state or owner."""
from dataclasses import dataclass
from datetime import datetime, timezone as dt_timezone
from hashlib import sha256
from pathlib import Path

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .store_config import APPLE_GROUP, BUNDLE_ID, PRODUCTS, StoreError, base_plan, config, environment


@dataclass(frozen=True)
class VerifiedSubscription:
    provider: str
    environment: str
    reference: str
    owner: str
    product_id: str
    plan: str
    state: str
    expires_at: datetime | None
    auto_renew: bool
    base_plan_id: str = ''
    purchase_token: str = ''
    linked_reference: str = ''


def plan_for(product):
    for plan, identifier in PRODUCTS.items():
        if product == identifier:
            return plan
    raise StoreError('This subscription product is not supported.', 400)


def milliseconds(value):
    return datetime.fromtimestamp(value / 1000, dt_timezone.utc) if value else None


def apple_services():
    from appstoreserverlibrary.api_client import AppStoreServerAPIClient
    from appstoreserverlibrary.models.Environment import Environment
    from appstoreserverlibrary.signed_data_verifier import SignedDataVerifier
    env = Environment.PRODUCTION if environment('apple') == 'production' else Environment.SANDBOX
    paths = config('APPLE_ROOT_CERT_PATHS').split(';')
    if not all(paths) or not config('APPLE_APP_ID'):
        raise StoreError()
    verifier = SignedDataVerifier([Path(p).read_bytes() for p in paths], True, env,
                                  BUNDLE_ID, int(config('APPLE_APP_ID')))
    client = AppStoreServerAPIClient(Path(config('APPLE_PRIVATE_KEY_PATH')).read_bytes(),
                                    config('APPLE_KEY_ID'), config('APPLE_ISSUER_ID'), BUNDLE_ID, env)
    return client, verifier


def verify_apple(transaction_id):
    client, verifier = apple_services()
    seed = verifier.verify_and_decode_signed_transaction(
        client.get_transaction_info(transaction_id).signedTransactionInfo)
    plan_for(seed.productId)
    if seed.bundleId != BUNDLE_ID or seed.subscriptionGroupIdentifier != APPLE_GROUP:
        raise StoreError('Subscription does not belong to this app.', 400)
    original = seed.originalTransactionId
    result = client.get_all_subscription_statuses(original)
    matches = []
    for group in result.data or []:
        if group.subscriptionGroupIdentifier != APPLE_GROUP:
            continue
        for item in group.lastTransactions or []:
            if item.originalTransactionId != original:
                continue
            tx = verifier.verify_and_decode_signed_transaction(item.signedTransactionInfo)
            renewal = verifier.verify_and_decode_renewal_info(item.signedRenewalInfo)
            if (tx.originalTransactionId != original or renewal.originalTransactionId != original
                    or tx.bundleId != BUNDLE_ID or tx.subscriptionGroupIdentifier != APPLE_GROUP
                    or not tx.appAccountToken or tx.inAppOwnershipType.value != 'PURCHASED'):
                raise StoreError('Subscription ownership could not be verified.', 409)
            expires = milliseconds(tx.expiresDate)
            state = 'expired'
            if item.status.value == 1:
                state = 'active'
            elif item.status.value == 4:
                state = 'grace'
                expires = milliseconds(renewal.gracePeriodExpiresDate)
            elif item.status.value == 3:
                state = 'billing_retry'
            if tx.revocationDate or item.status.value == 5:
                state = 'revoked'
            matches.append(VerifiedSubscription(
                'apple', environment('apple'), original, str(tx.appAccountToken).lower(),
                tx.productId, plan_for(tx.productId), state, expires,
                renewal.autoRenewStatus is not None and renewal.autoRenewStatus.value == 1))
    if len(matches) != 1:
        raise StoreError('Unable to establish the current subscription.', 409)
    return matches[0]


def google_session():
    import json

    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.service_account import Credentials

    credentials_json = config('GOOGLE_CREDENTIALS_JSON')
    if not credentials_json:
        raise StoreError('Google store credentials are not configured.')

    try:
        credentials_info = json.loads(credentials_json)
        credentials = Credentials.from_service_account_info(
            credentials_info,
            scopes=['https://www.googleapis.com/auth/androidpublisher'],
        )
    except (ValueError, TypeError, KeyError):
        raise StoreError('Google store credentials are invalid.') from None

    return AuthorizedSession(credentials)


def token_reference(token):
    return sha256(token.encode()).hexdigest()


def verify_google(token):
    from urllib.parse import quote
    with google_session() as session:
        response = session.get('https://androidpublisher.googleapis.com/androidpublisher/v3/'
            f'applications/{BUNDLE_ID}/purchases/subscriptionsv2/tokens/{quote(token, safe="")}', timeout=20)
        response.raise_for_status()
        data = response.json()
    env = 'sandbox' if 'testPurchase' in data else 'production'
    if env != environment('google'):
        raise StoreError('The purchase belongs to a different store environment.', 400)
    owner = (data.get('externalAccountIdentifiers') or {}).get('obfuscatedExternalAccountId')
    if not owner:
        raise StoreError('Subscription ownership could not be verified.', 409)
    items = data.get('lineItems', [])
    # Only simple monthly auto-renewing subscriptions are sold by this catalog.
    # Multi-item/replacement shapes require explicit support, never guess a plan.
    if len(items) != 1:
        raise StoreError('This subscription needs support to reconcile.', 409)
    item = items[0]
    plan = plan_for(item.get('productId'))
    base = (item.get('offerDetails') or {}).get('basePlanId')
    if not base or base != base_plan(plan) or 'autoRenewingPlan' not in item:
        raise StoreError('Subscription base plan is not configured.', 400)
    state = {
        'SUBSCRIPTION_STATE_ACTIVE': 'active',
        'SUBSCRIPTION_STATE_IN_GRACE_PERIOD': 'grace',
        'SUBSCRIPTION_STATE_CANCELED': 'canceled',
        'SUBSCRIPTION_STATE_PENDING': 'pending',
        'SUBSCRIPTION_STATE_PENDING_PURCHASE_CANCELED': 'expired',
        'SUBSCRIPTION_STATE_EXPIRED': 'expired',
        'SUBSCRIPTION_STATE_PAUSED': 'paused',
        'SUBSCRIPTION_STATE_ON_HOLD': 'on_hold',
    }.get(data.get('subscriptionState'))
    if not state:
        raise StoreError('Unrecognized store subscription state.', 409)
    expires = parse_datetime(item['expiryTime']) if item.get('expiryTime') else None
    if expires and timezone.is_naive(expires):
        raise StoreError('Invalid store expiry.', 400)
    linked = data.get('linkedPurchaseToken')
    return VerifiedSubscription('google', env, token_reference(token), owner,
        item['productId'], plan, state, expires, item['autoRenewingPlan'].get('autoRenewEnabled') is True,
        base, token, token_reference(linked) if linked else '')


def acknowledge_google(verified):
    """Called after durable entitlement storage; safely retried by client/RTDN."""
    if verified.state not in {'active', 'grace', 'canceled'}:
        return
    from urllib.parse import quote
    with google_session() as session:
        # Check acknowledgement first so repeated notifications remain idempotent.
        prefix = f'https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{BUNDLE_ID}/purchases/'
        result = session.get(prefix + 'subscriptionsv2/tokens/' + quote(verified.purchase_token, safe=''), timeout=20)
        result.raise_for_status()
        if result.json().get('acknowledgementState') == 'ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED':
            return
        result = session.post(prefix + 'subscriptions/' + quote(verified.product_id, safe='')
            + '/tokens/' + quote(verified.purchase_token, safe='') + ':acknowledge', json={}, timeout=20)
        result.raise_for_status()


def encrypt_token(token):
    from cryptography.fernet import Fernet
    return Fernet(config('TOKEN_ENCRYPTION_KEY').encode()).encrypt(token.encode()).decode()


def decrypt_token(token):
    from cryptography.fernet import Fernet
    return Fernet(config('TOKEN_ENCRYPTION_KEY').encode()).decrypt(token.encode()).decode()

