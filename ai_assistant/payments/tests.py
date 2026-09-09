import hashlib
import hmac
import json
import time
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth.models import User
from django.test import TestCase, Client
from django.urls import reverse
from ai_assistant.payments.models import StripeEvent

class StripeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='billing', email='test@example.com')
        self.client.force_login(self.user)
        self.url = reverse('payments:webhook')

    def subscription(self, amount=12900, status='active', sid='sub_test'):
        return {'id': sid, 'customer': 'cus_test', 'status': status,
                'metadata': {'user_id': str(self.user.pk), 'plan': 'pro'},
                'items': {'data': [{'quantity': 1, 'current_period_end': 1900000000,
                    'price': {'currency': 'sek', 'unit_amount': amount,
                              'recurring': {'interval': 'month'}}}]}}

    def send(self, obj, kind='customer.subscription.updated', eid='evt_test', subscription=None):
        event = {'id': eid, 'object': 'event', 'type': kind, 'livemode': False,
                 'data': {'object': obj}}
        body = json.dumps(event)
        timestamp = int(time.time())
        signature = hmac.new(b'whsec_local_test_only', f'{timestamp}.{body}'.encode(), hashlib.sha256).hexdigest()
        with patch('ai_assistant.payments.webhooks.stripe.Subscription.retrieve',
                   return_value=subscription or obj) as retrieve:
            response = self.client.post(self.url, body, content_type='application/json',
                HTTP_STRIPE_SIGNATURE=f't={timestamp},v1={signature}')
        self.user.profile.refresh_from_db()
        return response, retrieve

    def test_checkout_premium_and_pro(self):
        for plan, amount in [('premium', 12900), ('pro', 24900)]:
            with patch('ai_assistant.payments.views.stripe.checkout.Session.create',
                       return_value=SimpleNamespace(id='cs_test')) as create:
                response = self.client.post(reverse('payments:create_checkout_session'), {'plan': plan})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(create.call_args.kwargs['locale'], 'en')
            self.assertEqual(create.call_args.kwargs['line_items'][0]['price_data']['unit_amount'], amount)
            self.assertEqual(create.call_args.kwargs['subscription_data']['metadata']['plan'], plan)
            self.assertEqual(self.user.profile.plan, 'free')

    def test_checkout_completion_grants_access(self):
        session = {'mode': 'subscription', 'client_reference_id': str(self.user.pk),
                   'subscription': 'sub_test', 'customer': 'cus_test'}
        response, _ = self.send(session, 'checkout.session.completed', subscription=self.subscription())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.user.profile.plan, 'premium')
        self.assertIsNotNone(self.user.profile.subscription_current_period_end)

    def test_upgrade_downgrade_cancel_and_recovery(self):
        for i, (amount, status, expected) in enumerate([
            (12900, 'active', 'premium'), (24900, 'active', 'pro'),
            (12900, 'active', 'premium'), (12900, 'past_due', 'free'),
            (12900, 'active', 'premium'), (12900, 'canceled', 'free'),
            (24900, 'trialing', 'pro'), (24900, 'unpaid', 'free'),
            (24900, 'incomplete', 'free'), (24900, 'paused', 'free')]):
            response, _ = self.send(self.subscription(amount, status), eid=f'evt_{i}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.user.profile.plan, expected)

    def test_scheduled_cancel_preserves_access(self):
        sub = self.subscription()
        sub['cancel_at_period_end'] = True
        self.send(sub)
        self.assertEqual(self.user.profile.plan, 'premium')

    def test_duplicate_does_not_retrieve_again(self):
        self.send(self.subscription())
        response, retrieve = self.send(self.subscription())
        self.assertEqual(response.status_code, 200)
        retrieve.assert_not_called()
        self.assertEqual(StripeEvent.objects.count(), 1)

    def test_old_event_uses_current_state(self):
        self.send(self.subscription(24900), subscription=self.subscription(12900))
        self.assertEqual(self.user.profile.plan, 'premium')

    def test_old_subscription_cannot_revoke_current(self):
        self.send(self.subscription())
        response, retrieve = self.send(self.subscription(status='canceled', sid='sub_old'),
                                      'customer.subscription.deleted', 'evt_old')
        self.assertEqual(response.status_code, 200)
        retrieve.assert_not_called()
        self.assertEqual(self.user.profile.plan, 'premium')

    def test_unknown_price_is_not_paid(self):
        self.send(self.subscription(1))
        self.assertEqual(self.user.profile.plan, 'free')

    def test_signature_and_method_rejected(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.assertEqual(self.client.post(self.url, '{}', content_type='application/json').status_code, 400)

    def test_provider_failure_is_retryable(self):
        # Patch the helper's mock response to fail when the reconciler reads it.
        class Broken(dict):
            def get(self, *args):
                raise RuntimeError('provider secret')
        response, _ = self.send(self.subscription(), subscription=Broken(x=1))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(StripeEvent.objects.count(), 0)
        self.assertNotIn(b'provider secret', response.content)
        self.assertEqual(self.send(self.subscription())[0].status_code, 200)

    def test_checkout_auth_csrf_and_existing_subscription(self):
        url = reverse('payments:create_checkout_session')
        self.assertEqual(Client().post(url).status_code, 302)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(url).status_code, 403)
        self.send(self.subscription())
        with patch('ai_assistant.payments.views.stripe.checkout.Session.create') as create:
            self.assertEqual(self.client.post(url, {'plan': 'pro'}).status_code, 409)
            create.assert_not_called()

    def test_invalid_plan_and_provider_error(self):
        url = reverse('payments:create_checkout_session')
        self.assertEqual(self.client.post(url, {'plan': 'invalid'}).status_code, 400)
        with patch('ai_assistant.payments.views.stripe.checkout.Session.create',
                   side_effect=RuntimeError('secret')):
            response = self.client.post(url, {'plan': 'premium'})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn(b'secret', response.content)

    def test_subscription_customer_mismatch_preserves_free_access(self):
        current = self.subscription()
        current['customer'] = 'cus_different'
        response, _ = self.send(self.subscription(), subscription=current)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.user.profile.plan, 'free')
        self.assertFalse(StripeEvent.objects.exists())

    def test_subscription_owner_mismatch_preserves_free_access(self):
        current = self.subscription()
        current['metadata']['user_id'] = '99999'
        response, _ = self.send(self.subscription(), subscription=current)
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.user.profile.plan, 'free')
        self.assertFalse(StripeEvent.objects.exists())

    def test_non_subscription_checkout_does_not_grant_access(self):
        response, retrieve = self.send({'mode':'payment'}, 'checkout.session.completed')
        self.assertEqual(response.status_code, 200)
        retrieve.assert_not_called()
        self.assertEqual(self.user.profile.plan, 'free')

    def test_invalid_price_shapes_do_not_grant_access(self):
        variants = []
        for field, value in [('currency','usd'), ('unit_amount',0)]:
            sub = self.subscription()
            sub['items']['data'][0]['price'][field] = value
            variants.append(sub)
        sub = self.subscription()
        sub['items']['data'][0]['price']['recurring']['interval'] = 'year'
        variants.append(sub)
        sub = self.subscription()
        sub['items']['data'][0]['quantity'] = 2
        variants.append(sub)
        for i, sub in enumerate(variants):
            response, _ = self.send(sub, eid=f'evt_invalid_price_{i}')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.user.profile.plan, 'free')

    def test_live_event_rejected_with_test_key_before_provider_call(self):
        body = json.dumps({'id':'evt_live_rejected', 'object':'event', 'type':'customer.subscription.updated',
                           'livemode':True, 'data':{'object':self.subscription()}})
        timestamp = int(time.time())
        signature = hmac.new(b'whsec_local_test_only', f'{timestamp}.{body}'.encode(), hashlib.sha256).hexdigest()
        with patch('ai_assistant.payments.webhooks.stripe.Subscription.retrieve') as retrieve:
            response = self.client.post(self.url, body, content_type='application/json',
                HTTP_STRIPE_SIGNATURE=f't={timestamp},v1={signature}')
        self.assertEqual(response.status_code, 400)
        retrieve.assert_not_called()
        self.assertFalse(StripeEvent.objects.exists())

    def test_malformed_signed_events_leave_paid_entitlements_unchanged(self):
        from copy import deepcopy
        self.send(self.subscription(24900))
        def snapshot():
            return type(self.user.profile).objects.filter(pk=self.user.profile.pk).values().get()
        before = snapshot()
        receipts = StripeEvent.objects.count()
        valid = {'id':'evt_bad', 'object':'event', 'type':'customer.subscription.updated',
                 'livemode':False, 'data':{'object':self.subscription()}}
        variants = [[], None, 'invalid', {}, dict(valid, type=[]), dict(valid, livemode='false'),
                    dict(valid, data=[]), dict(valid, data={'object': []}), dict(valid, id=[])]
        for field, value in [('id', {}), ('customer', []), ('metadata', ['bad'])]:
            event = deepcopy(valid)
            event['data']['object'][field] = value
            variants.append(event)
        event = deepcopy(valid)
        event['data']['object']['metadata']['user_id'] = '9' * 5000
        variants.append(event)
        for event in variants:
            with self.subTest(event_type=type(event).__name__):
                body = json.dumps(event)
                timestamp = int(time.time())
                signature = hmac.new(b'whsec_local_test_only', f'{timestamp}.{body}'.encode(), hashlib.sha256).hexdigest()
                with patch('ai_assistant.payments.webhooks.stripe.Subscription.retrieve') as retrieve:
                    response = self.client.post(self.url, body, content_type='application/json',
                        HTTP_STRIPE_SIGNATURE=f't={timestamp},v1={signature}')
                self.assertEqual(response.status_code, 400)
                retrieve.assert_not_called()
                self.assertEqual(snapshot(), before)
                self.assertEqual(StripeEvent.objects.count(), receipts)

    def test_bad_signature_leaves_paid_entitlements_unchanged(self):
        self.send(self.subscription(24900))
        before = type(self.user.profile).objects.filter(pk=self.user.profile.pk).values().get()
        with patch('ai_assistant.payments.webhooks.stripe.Subscription.retrieve') as retrieve:
            response = self.client.post(self.url, '{}', content_type='application/json', HTTP_STRIPE_SIGNATURE='invalid')
        self.assertEqual(response.status_code, 400)
        retrieve.assert_not_called()
        self.assertEqual(type(self.user.profile).objects.filter(pk=self.user.profile.pk).values().get(), before)
        self.assertEqual(StripeEvent.objects.count(), 1)

    def test_wrong_retrieved_subscription_preserves_paid_entitlements(self):
        self.send(self.subscription(24900))
        response, _ = self.send(self.subscription(), eid='evt_wrong_sub', subscription=self.subscription(sid='sub_wrong'))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.user.profile.plan, 'pro')
        self.assertEqual(StripeEvent.objects.count(), 1)
