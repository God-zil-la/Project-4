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

class PortalTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="portal-owner")
        self.user.profile.stripe_customer_id = "cus_owner"
        self.user.profile.stripe_subscription_id = "sub_owner"
        self.user.profile.stripe_subscription_status = "active"
        self.user.profile.save()
        self.client.force_login(self.user)
        self.url = reverse("payments:create_portal_session")
        self.portal = patch("ai_assistant.payments.views.stripe.billing_portal.Session.create")
        self.create = self.portal.start()
        self.addCleanup(self.portal.stop)
        self.create.return_value = SimpleNamespace(url="https://billing.stripe.com/p/session/test_session")

    def test_owner_and_fixed_return_url_with_test_key(self):
        with self.settings(STRIPE_SECRET_KEY="sk_test_placeholder"):
            response = self.client.post(self.url, {
                "customer": "cus_other", "subscription": "sub_other",
                "return_url": "https://example.org/", "next": "//example.org/",
            })
        self.assertEqual(response.status_code, 303)
        self.assertEqual(response["Location"], self.create.return_value.url)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.create.assert_called_once_with(
            api_key="sk_test_placeholder", customer="cus_owner", locale="en",
            return_url="http://testserver/payments/",
        )
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.stripe_subscription_id, "sub_owner")

    def test_login_required(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.create.assert_not_called()

    def test_post_only(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
        self.create.assert_not_called()

    def test_csrf_required_and_billing_form_works(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url).status_code, 403)
        self.create.assert_not_called()
        response = client.get(reverse("payments:billing"))
        self.assertContains(response, 'action="' + self.url + '"')
        self.assertContains(response, "Manage subscription")
        self.assertEqual(client.post(self.url, {
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        }).status_code, 303)

    def test_missing_customer_cannot_use_submitted_customer(self):
        self.user.profile.stripe_customer_id = ""
        self.user.profile.save()
        response = self.client.post(self.url, {"customer": "cus_other"}, follow=True)
        self.assertContains(response, "No billing account is available to manage.")
        self.assertContains(response, "missing its billing account link")
        self.create.assert_not_called()

    def test_customer_without_current_subscription_can_manage_billing(self):
        self.user.profile.stripe_subscription_id = ""
        self.user.profile.save()
        self.assertEqual(self.client.post(self.url).status_code, 303)

    def test_missing_key(self):
        with self.settings(STRIPE_SECRET_KEY=""):
            response = self.client.post(self.url, follow=True)
        self.assertContains(response, "Billing is temporarily unavailable.")
        self.create.assert_not_called()

    def test_provider_errors_are_sanitized(self):
        self.create.side_effect = Exception("private-provider-detail")
        response = self.client.post(self.url, follow=True)
        self.assertContains(response, "Unable to open subscription management. Please try again later.")
        self.assertNotContains(response, "private-provider-detail")

    def test_unsafe_provider_destination_is_rejected(self):
        for url in ["http://billing.stripe.com/session", "https://example.org/", "javascript:alert(1)"]:
            self.create.return_value = SimpleNamespace(url=url)
            response = self.client.post(self.url)
            self.assertRedirects(response, reverse("payments:billing"))

    def test_portal_does_not_remove_duplicate_subscription_protection(self):
        self.client.post(self.url)
        with patch("ai_assistant.payments.views.stripe.checkout.Session.create") as checkout:
            response = self.client.post(reverse("payments:create_checkout_session"))
        self.assertEqual(response.status_code, 409)
        checkout.assert_not_called()


class StripeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='billing', email='test@example.com')
        self.client.force_login(self.user)
        self.url = reverse('payments:webhook')

    def subscription(self, amount=1299, status='active', sid='sub_test'):
        return {'id': sid, 'customer': 'cus_test', 'status': status,
                'metadata': {'user_id': str(self.user.pk), 'plan': 'pro'},
                'items': {'data': [{'quantity': 1, 'current_period_end': 1900000000,
                    'price': {'currency': 'usd', 'unit_amount': amount,
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
        for plan, amount in [('premium', 1299), ('pro', 2499)]:
            with patch('ai_assistant.payments.views.stripe.checkout.Session.create',
                       return_value=SimpleNamespace(id='cs_test')) as create:
                response = self.client.post(reverse('payments:create_checkout_session'), {'plan': plan})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(create.call_args.kwargs['locale'], 'en')
            self.assertEqual(create.call_args.kwargs['mode'], 'subscription')
            self.assertEqual(create.call_args.kwargs['line_items'][0]['quantity'], 1)
            self.assertEqual(create.call_args.kwargs['line_items'][0]['price_data']['currency'], 'usd')
            self.assertEqual(create.call_args.kwargs['line_items'][0]['price_data']['recurring'], {'interval': 'month'})
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
            (1299, 'active', 'premium'), (2499, 'active', 'pro'),
            (1299, 'active', 'premium'), (1299, 'past_due', 'free'),
            (1299, 'active', 'premium'), (1299, 'canceled', 'free'),
            (2499, 'trialing', 'pro'), (2499, 'unpaid', 'free'),
            (2499, 'incomplete', 'free'), (2499, 'paused', 'free')]):
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
        self.send(self.subscription(2499), subscription=self.subscription(1299))
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

    def test_legacy_and_incorrect_prices_revoke_paid_access(self):
        for i, (currency, amount) in enumerate([
            ('sek', 12900), ('sek', 24900), ('sek', 1299), ('sek', 2499),
            ('usd', 12900), ('usd', 24900), ('usd', 1298), ('usd', 2500),
        ]):
            with self.subTest(currency=currency, amount=amount):
                self.send(self.subscription(2499), eid=f'evt_paid_{i}')
                self.assertEqual(self.user.profile.plan, 'pro')
                sub = self.subscription(amount)
                sub['items']['data'][0]['price']['currency'] = currency
                response, _ = self.send(sub, eid=f'evt_wrong_price_{i}')
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.user.profile.plan, 'free')
                self.assertFalse(self.user.profile.is_subscribed)

    def test_checkout_completion_reconciles_both_usd_plans(self):
        for i, (amount, plan) in enumerate([(1299, 'premium'), (2499, 'pro')]):
            session = {'mode': 'subscription', 'client_reference_id': str(self.user.pk),
                       'subscription': 'sub_test', 'customer': 'cus_test'}
            response, _ = self.send(session, 'checkout.session.completed',
                eid=f'evt_checkout_{i}', subscription=self.subscription(amount))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(self.user.profile.plan, plan)

    def test_customer_facing_usd_prices(self):
        for url in [reverse('payments:billing'), reverse('dashboard:home')]:
            response = self.client.get(url)
            self.assertContains(response, '$12.99 USD/month')
            self.assertContains(response, '$24.99 USD/month')
            self.assertNotContains(response, 'SEK')

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
        for field, value in [('currency','sek'), ('unit_amount',0)]:
            sub = self.subscription()
            sub['items']['data'][0]['price'][field] = value
            variants.append(sub)
        sub = self.subscription()
        sub['items']['data'][0]['price']['recurring']['interval'] = 'year'
        variants.append(sub)
        sub = self.subscription()
        sub['items']['data'][0]['price']['recurring']['interval_count'] = 2
        variants.append(sub)
        sub = self.subscription()
        sub['items']['data'] *= 2
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
        self.send(self.subscription(2499))
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
        self.send(self.subscription(2499))
        before = type(self.user.profile).objects.filter(pk=self.user.profile.pk).values().get()
        with patch('ai_assistant.payments.webhooks.stripe.Subscription.retrieve') as retrieve:
            response = self.client.post(self.url, '{}', content_type='application/json', HTTP_STRIPE_SIGNATURE='invalid')
        self.assertEqual(response.status_code, 400)
        retrieve.assert_not_called()
        self.assertEqual(type(self.user.profile).objects.filter(pk=self.user.profile.pk).values().get(), before)
        self.assertEqual(StripeEvent.objects.count(), 1)

    def test_wrong_retrieved_subscription_preserves_paid_entitlements(self):
        self.send(self.subscription(2499))
        response, _ = self.send(self.subscription(), eid='evt_wrong_sub', subscription=self.subscription(sid='sub_wrong'))
        self.assertEqual(response.status_code, 500)
        self.assertEqual(self.user.profile.plan, 'pro')
        self.assertEqual(StripeEvent.objects.count(), 1)


class BillingStateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="billing-states")
        self.client.force_login(self.user)

    def test_existing_subscription_has_management_and_no_checkout_script(self):
        profile = self.user.profile
        profile.stripe_customer_id = "cus_owner"
        profile.stripe_subscription_id = "sub_owner"
        profile.stripe_subscription_status = "active"
        profile.save()
        response = self.client.get(reverse("payments:billing"))
        self.assertContains(response, "Manage subscription")
        self.assertTrue(response.context["can_manage_subscription"])
        self.assertFalse(response.context["can_checkout"])
        self.assertNotContains(response, "https://js.stripe.com/v3/")

    def test_missing_customer_explains_block_and_preserves_checkout_guard(self):
        profile = self.user.profile
        profile.stripe_subscription_id = "sub_owner"
        profile.save()
        response = self.client.get(reverse("payments:billing"))
        self.assertContains(response, "missing its billing account link")
        self.assertFalse(response.context["can_manage_subscription"])
        self.assertFalse(response.context["can_checkout"])
        self.assertEqual(self.client.post(reverse("payments:create_checkout_session")).status_code, 409)

    def test_missing_keys_explained_without_stripe_javascript(self):
        with self.settings(STRIPE_SECRET_KEY="", STRIPE_PUBLIC_KEY=""):
            response = self.client.get(reverse("payments:billing"))
        self.assertContains(response, "Billing is not configured in this environment")
        self.assertNotContains(response, "https://js.stripe.com/v3/")
        self.assertFalse(response.context["can_checkout"])

    def test_ended_subscriptions_can_checkout(self):
        for status in ["canceled", "incomplete_expired"]:
            profile = self.user.profile
            profile.stripe_subscription_id = "sub_old"
            profile.stripe_subscription_status = status
            profile.save()
            with self.settings(STRIPE_PUBLIC_KEY="pk_test_placeholder"):
                response = self.client.get(reverse("payments:billing"))
            self.assertTrue(response.context["can_checkout"])

    def test_alternate_template_matches_active_template(self):
        from pathlib import Path
        from django.conf import settings
        from django.template.loader import get_template
        active = Path(settings.BASE_DIR) / "templates/payments/billing.html"
        alternate = Path(settings.BASE_DIR) / "payments/templates/payments/billing.html"
        self.assertEqual(Path(get_template("payments/billing.html").origin.name), active)
        self.assertEqual(active.read_text(encoding="utf-8"), alternate.read_text(encoding="utf-8"))
