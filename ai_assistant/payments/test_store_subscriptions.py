from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from cryptography.fernet import Fernet
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from ai_assistant.accounts.deletion import DeletionBlocked, check_billing
from .models import CheckoutAttempt, StoreEvent, StoreSubscription
from .state import clear_subscription
from .store_config import APPLE_GROUP, BUNDLE_ID, PRODUCTS, StoreError
from .store_notifications import process
from .store_service import apply_verified, identity_for, reconcile_web_checkout, start_purchase, verify_purchase
from .store_verification import VerifiedSubscription, decrypt_token, verify_apple, verify_google


@override_settings(STORE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode(),
                   STORE_APPLE_ENVIRONMENT='sandbox', STORE_GOOGLE_ENVIRONMENT='sandbox',
                   STORE_GOOGLE_PREMIUM_BASE_PLAN_ID='monthly', STORE_GOOGLE_PRO_BASE_PLAN_ID='monthly')
class StoreTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('store-owner', password='test-password')
        self.other = User.objects.create_user('other-owner', password='test-password')
        self.profile = self.user.profile
        self.identity = identity_for(self.profile)
        self.verified = VerifiedSubscription('apple', 'sandbox', 'original-1', str(self.identity.token),
            PRODUCTS['pro'], 'pro', 'active', timezone.now() + timedelta(days=30), True)
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def apply(self, verified=None):
        with transaction.atomic():
            return apply_verified(self.profile, verified or self.verified)

    def test_store_entitlement_survives_stripe_clear(self):
        self.apply()
        clear_subscription(self.profile)
        self.assertEqual(self.profile.effective_plan, 'pro')
        self.assertEqual(self.profile.plan, 'free')
        self.assertEqual(self.api.get('/accounts/api/me/').json()['plan'], 'pro')

    def test_highest_of_three_providers_and_complimentary(self):
        self.apply(replace(self.verified, plan='premium', product_id=PRODUCTS['premium']))
        self.profile.plan = 'pro'
        self.assertEqual(self.profile.effective_plan, 'pro')
        self.profile.plan = 'free'
        self.profile.complimentary_plan = 'pro'
        self.assertEqual(self.profile.effective_plan, 'pro')
        self.profile.complimentary_until = timezone.now() - timedelta(seconds=1)
        self.assertEqual(self.profile.effective_plan, 'premium')

    def test_expiry_revocation_pending_and_billing_hold_fail_closed(self):
        for state in ['pending', 'revoked', 'expired', 'on_hold', 'paused', 'billing_retry']:
            self.apply(replace(self.verified, state=state))
            self.assertEqual(self.profile.effective_plan, 'free', state)
        for state in ['active', 'grace', 'canceled']:
            self.apply(replace(self.verified, state=state))
            self.assertEqual(self.profile.effective_plan, 'pro', state)
        self.apply(replace(self.verified, expires_at=timezone.now() - timedelta(seconds=1)))
        self.assertEqual(self.profile.effective_plan, 'free')

    def test_idempotent_and_wrong_account_is_rejected(self):
        self.apply()
        self.apply()
        self.assertEqual(StoreSubscription.objects.count(), 1)
        with self.assertRaises(StoreError), transaction.atomic():
            apply_verified(self.other.profile, self.verified)
        self.assertEqual(self.other.profile.effective_plan, 'free')

    def test_reference_cannot_be_rebound_with_different_owner(self):
        self.apply()
        other_identity = identity_for(self.other.profile)
        with self.assertRaises(StoreError), transaction.atomic():
            apply_verified(self.other.profile, replace(self.verified, owner=str(other_identity.token)))

    @patch('ai_assistant.payments.store_service.configured', return_value=True)
    def test_intent_retry_and_cross_provider_mutex(self, _):
        first = start_purchase(self.user, 'apple', PRODUCTS['pro'])
        self.assertEqual(first.pk, start_purchase(self.user, 'apple', PRODUCTS['pro']).pk)
        with self.assertRaises(StoreError):
            start_purchase(self.user, 'google', PRODUCTS['premium'])
        self.client.force_login(self.user)
        for key in ['', 'sk_test_placeholder']:
            with self.subTest(stripe_configured=bool(key)), override_settings(STRIPE_SECRET_KEY=key), patch('stripe.checkout.Session.create') as create:
                response = self.client.post('/payments/create-checkout-session/', {'plan': 'premium'})
                self.assertEqual(response.status_code, 409)
                create.assert_not_called()

    @override_settings(STRIPE_SECRET_KEY='')
    @patch('ai_assistant.payments.views.reconcile_customer')
    @patch('stripe.checkout.Session.create')
    def test_missing_stripe_key_preserves_store_conflict(self, create, reconcile):
        self.client.force_login(self.user)
        response = self.client.post('/payments/create-checkout-session/', {'plan': 'premium'})
        self.assertEqual(response.status_code, 503)
        self.apply()
        response = self.client.post('/payments/create-checkout-session/', {'plan': 'premium'})
        self.assertEqual(response.status_code, 409)
        self.assertFalse(CheckoutAttempt.objects.filter(profile=self.profile).exists())
        reconcile.assert_not_called()
        create.assert_not_called()

    @patch('ai_assistant.payments.store_service.configured', return_value=True)
    def test_stripe_and_web_checkout_block_native(self, _):
        self.profile.stripe_subscription_id = 'sub_existing'
        self.profile.stripe_subscription_status = 'active'
        self.profile.save()
        with self.assertRaises(StoreError):
            start_purchase(self.user, 'apple', PRODUCTS['pro'])
        clear_subscription(self.profile)
        CheckoutAttempt.objects.create(profile=self.profile, plan='pro', success_url='https://example.test', cancel_url='https://example.test')
        with self.assertRaises(StoreError):
            start_purchase(self.user, 'apple', PRODUCTS['pro'])

    def test_missing_credentials_never_grant_access(self):
        result = self.api.post('/payments/api/store/verify/', {'provider': 'apple', 'reference': '1'})
        self.assertEqual(result.status_code, 503)
        self.assertEqual(StoreSubscription.objects.count(), 0)
        catalog = self.api.get('/payments/api/store/catalog/?provider=apple').json()
        self.assertFalse(catalog['available'])
        self.assertEqual(catalog['products'][1]['product_id'], PRODUCTS['pro'])

    def test_authentication_and_no_cache(self):
        anonymous = APIClient()
        self.assertEqual(anonymous.get('/payments/api/store/status/').status_code, 401)
        result = self.api.get('/payments/api/store/status/')
        self.assertEqual(result['Cache-Control'], 'no-store')
        self.assertNotIn('account_token', result.json())

    def test_store_blocks_automatic_deletion(self):
        self.apply()
        with self.assertRaises(DeletionBlocked):
            check_billing(self.profile)

    def test_sandbox_access_is_not_granted_in_production(self):
        self.apply()
        with override_settings(STORE_APPLE_ENVIRONMENT='production'):
            self.assertEqual(self.profile.effective_plan, 'free')

    @patch('stripe.checkout.Session.list')
    def test_legacy_open_stripe_session_blocks_native(self, sessions):
        self.profile.stripe_customer_id = 'cus_1'
        sessions.return_value.auto_paging_iter.return_value = iter([
            {'id': 'cs_old', 'customer': 'cus_1', 'mode': 'subscription', 'status': 'open'}])
        with self.assertRaises(StoreError):
            reconcile_web_checkout(self.profile)

    def test_old_google_token_cannot_resurrect_replaced_entitlement(self):
        self.apply(replace(self.verified, state='replaced'))
        self.apply(self.verified)
        self.assertEqual(self.profile.effective_plan, 'free')

    def test_tombstone_prevents_transfer_after_deletion(self):
        self.apply(replace(self.verified, state='expired'))
        self.user.delete()
        self.identity.refresh_from_db()
        self.assertIsNone(self.identity.profile_id)
        self.assertTrue(StoreSubscription.objects.filter(identity=self.identity).exists())

    @patch('ai_assistant.payments.store_service.configured', return_value=True)
    @patch('ai_assistant.payments.store_verification.acknowledge_google')
    @patch('ai_assistant.payments.store_verification.verify_google')
    def test_google_encrypted_token_commit_and_retry(self, verify, acknowledge, _):
        verify.return_value = replace(self.verified, provider='google', purchase_token='private-token', reference='hash')
        acknowledge.side_effect = RuntimeError('network failure')
        with self.assertRaises(RuntimeError):
            verify_purchase(self.user, 'google', 'private-token')
        row = StoreSubscription.objects.get()
        self.assertNotIn('private-token', row.encrypted_token)
        self.assertEqual(decrypt_token(row.encrypted_token), 'private-token')
        self.assertEqual(self.profile.effective_plan, 'pro')
        acknowledge.side_effect = None
        verify_purchase(self.user, 'google', 'private-token')
        self.assertEqual(StoreSubscription.objects.count(), 1)

    @patch('ai_assistant.payments.store_notifications.verify_purchase')
    def test_notification_only_marks_success_and_deduplicates(self, verify):
        verify.side_effect = StoreError()
        with self.assertRaises(StoreError):
            process('apple', 'event-1', str(self.identity.token), 'tx')
        self.assertEqual(StoreEvent.objects.count(), 0)
        verify.side_effect = None
        process('apple', 'event-1', str(self.identity.token), 'tx')
        process('apple', 'event-1', str(self.identity.token), 'tx')
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(StoreEvent.objects.count(), 1)

    def test_unsigned_google_notification_rejected(self):
        with override_settings(STORE_GOOGLE_PUBSUB_AUDIENCE='https://example.test/push',
                               STORE_GOOGLE_PUBSUB_SERVICE_ACCOUNT='pubsub@example.test'):
            result = self.client.post('/payments/notifications/google/', {}, content_type='application/json')
        self.assertEqual(result.status_code, 401)

    @override_settings(STORE_GOOGLE_CREDENTIALS_JSON='{"type":"service_account","private_key":"dummy-test-only"}')
    @patch('google.auth.transport.requests.AuthorizedSession')
    @patch('google.oauth2.service_account.Credentials.from_service_account_info')
    def test_google_credentials_loaded_from_json(self, credentials, session):
        from .store_verification import google_session
        self.assertIs(google_session(), session.return_value)
        credentials.assert_called_once_with(
            {'type': 'service_account', 'private_key': 'dummy-test-only'},
            scopes=['https://www.googleapis.com/auth/androidpublisher'])
        session.assert_called_once_with(credentials.return_value)

    def test_missing_or_malformed_google_credentials_fail_closed(self):
        from .store_verification import google_session
        for value in ['', 'invalid-json', '{}']:
            with self.subTest(value=value), override_settings(STORE_GOOGLE_CREDENTIALS_JSON=value):
                with self.assertRaises(StoreError) as error:
                    google_session()
                self.assertEqual(error.exception.status, 503)

    @override_settings(STORE_GOOGLE_CREDENTIALS_JSON='{"private_key":"dummy-test-only"}')
    @patch('google.oauth2.service_account.Credentials.from_service_account_info',
           side_effect=ValueError('private-provider-detail'))
    def test_google_credentials_errors_do_not_expose_secrets(self, credentials):
        from .store_verification import google_session
        with self.assertRaises(StoreError) as error:
            google_session()
        self.assertEqual(str(error.exception), 'Google store credentials are invalid.')

    @patch('ai_assistant.payments.store_verification.google_session')
    def test_google_authoritative_base_plan_and_environment(self, session):
        data = {'testPurchase': {}, 'externalAccountIdentifiers': {'obfuscatedExternalAccountId': str(self.identity.token)},
                'subscriptionState': 'SUBSCRIPTION_STATE_ACTIVE', 'lineItems': [{
                    'productId': PRODUCTS['pro'], 'expiryTime': '2030-01-01T00:00:00Z',
                    'autoRenewingPlan': {'autoRenewEnabled': True}, 'offerDetails': {'basePlanId': 'monthly'}}]}
        session.return_value.__enter__.return_value.get.return_value.json.return_value = data
        self.assertEqual(verify_google('token').plan, 'pro')
        data['lineItems'][0]['offerDetails']['basePlanId'] = 'unapproved'
        with self.assertRaises(StoreError):
            verify_google('token')
        data['lineItems'][0]['offerDetails']['basePlanId'] = 'monthly'
        del data['testPurchase']
        with self.assertRaises(StoreError):
            verify_google('token')

    @patch('ai_assistant.payments.store_verification.apple_services')
    def test_apple_fetches_current_status_instead_of_replaying_receipt(self, services):
        client, verifier = Mock(), Mock()
        services.return_value = client, verifier
        tx = NS(productId=PRODUCTS['pro'], bundleId=BUNDLE_ID, subscriptionGroupIdentifier=APPLE_GROUP,
                originalTransactionId='original-1', appAccountToken=str(self.identity.token),
                inAppOwnershipType=NS(value='PURCHASED'), expiresDate=1900000000000, revocationDate=None)
        verifier.verify_and_decode_signed_transaction.return_value = tx
        verifier.verify_and_decode_renewal_info.return_value = NS(originalTransactionId='original-1',
            autoRenewStatus=NS(value=1), gracePeriodExpiresDate=1900000100000)
        item = NS(originalTransactionId='original-1', signedTransactionInfo='jws', signedRenewalInfo='renewal', status=NS(value=5))
        client.get_all_subscription_statuses.return_value = NS(data=[NS(subscriptionGroupIdentifier=APPLE_GROUP, lastTransactions=[item])])
        self.assertEqual(verify_apple('old-transaction').state, 'revoked')
        client.get_all_subscription_statuses.assert_called_once_with('original-1')
        item.status.value = 4
        self.assertEqual(verify_apple('old-transaction').state, 'grace')
        tx.inAppOwnershipType.value = 'FAMILY_SHARED'
        with self.assertRaises(StoreError):
            verify_apple('old-transaction')
