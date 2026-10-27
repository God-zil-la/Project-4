from datetime import timedelta
from unittest.mock import Mock

from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from .campaign import TOKEN_LIMIT, campaign_scope, provider_call, redeem
from .models import UserProfile


@override_settings(K1_CAMPAIGN_ENABLED=True, K1_CAMPAIGN_CODE='test-campaign')
class CampaignTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('campaign-user', password='test-password')
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)

    def activate(self):
        redeem(self.user, 'test-campaign')
        self.profile.refresh_from_db()

    def call(self, provider, **kwargs):
        @campaign_scope
        def invoke(user):
            return provider_call(provider, model='gpt-4o-mini',
                                 messages=[{'role': 'user', 'content': 'Hello'}],
                                 max_tokens=100, **kwargs)
        return invoke(self.user)

    def test_activation_and_single_redemption_after_expiry(self):
        self.activate()
        self.assertEqual(self.profile.campaign_ends_at - self.profile.campaign_started_at, timedelta(days=14))
        self.assertEqual(self.profile.effective_plan, 'pro')
        self.assertEqual(self.profile.plan, 'free')
        UserProfile.objects.filter(pk=self.profile.pk).update(campaign_ends_at=timezone.now())
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.effective_plan, 'free')
        with self.assertRaises(ValueError):
            redeem(self.user, 'test-campaign')

    def test_invalid_and_disabled_codes_do_not_activate(self):
        with self.assertRaises(ValueError):
            redeem(self.user, 'wrong')
        with override_settings(K1_CAMPAIGN_ENABLED=False), self.assertRaises(ValueError):
            redeem(self.user, 'test-campaign')
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.campaign_started_at)

    def test_paid_complimentary_and_inactive_accounts_are_ineligible(self):
        for changes in ({'plan': 'premium'}, {'plan': 'pro'},
                        {'plan': 'free', 'complimentary_plan': 'premium'}):
            UserProfile.objects.filter(pk=self.profile.pk).update(**changes)
            with self.assertRaises(ValueError):
                redeem(self.user, 'test-campaign')
        UserProfile.objects.filter(pk=self.profile.pk).update(complimentary_plan='')
        self.user.is_active = False
        with self.assertRaises(ValueError):
            redeem(self.user, 'test-campaign')

    def test_web_requires_session_csrf_and_post(self):
        url = reverse('accounts:campaign')
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.get(url).status_code, 302)
        client.force_login(self.user)
        self.assertEqual(client.get(url).status_code, 200)
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.campaign_started_at)
        self.assertEqual(client.post(url, {'code': 'test-campaign'}).status_code, 403)
        token = client.cookies['csrftoken'].value
        response = client.post(url, {'code': 'test-campaign', 'csrfmiddlewaretoken': token})
        self.assertContains(response, 'Your 14-day Free Pro campaign has started successfully.')

    def test_actual_input_output_and_embedding_share_counter(self):
        self.activate()
        self.call(Mock(return_value={'usage': {'prompt_tokens': 20, 'completion_tokens': 30}}))
        provider_call(Mock(return_value={'usage': {'prompt_tokens': 40}}),
                      campaign_user=self.user, model='text-embedding-3-small', input=['document'])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.campaign_tokens, 90)
        self.assertEqual(self.profile.campaign_reserved_tokens, 0)

    def test_inflight_reservation_blocks_competing_request(self):
        self.activate()
        UserProfile.objects.filter(pk=self.profile.pk).update(campaign_tokens=TOKEN_LIMIT - 600)
        competitor = Mock()
        def first_provider(**kwargs):
            from ai_assistant.bots.chat_service import ChatUsageLimitError
            with self.assertRaises(ChatUsageLimitError):
                self.call(competitor)
            return {'usage': {'prompt_tokens': 20, 'completion_tokens': 30}}
        self.call(first_provider)
        competitor.assert_not_called()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.campaign_tokens, TOKEN_LIMIT - 550)
        self.assertEqual(self.profile.campaign_reserved_tokens, 0)

    def test_failure_and_missing_usage_are_charged_conservatively(self):
        self.activate()
        with self.assertRaises(TimeoutError):
            self.call(Mock(side_effect=TimeoutError))
        self.profile.refresh_from_db()
        first = self.profile.campaign_tokens
        self.assertGreater(first, 100)
        self.call(Mock(return_value={}))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.campaign_tokens, first * 2)
        self.assertEqual(self.profile.campaign_reserved_tokens, 0)

    def test_cap_preserves_data_and_ordinary_paid_plan(self):
        self.activate()
        UserProfile.objects.filter(pk=self.profile.pk).update(campaign_tokens=TOKEN_LIMIT)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.effective_plan, 'pro')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.profile.plan = 'premium'
        self.profile.save(update_fields=['plan'])
        self.assertEqual(self.profile.effective_plan, 'pro')

    def test_expiry_between_scope_and_provider_blocks_call(self):
        self.activate()
        provider = Mock()
        @campaign_scope
        def invoke(user):
            UserProfile.objects.filter(pk=self.profile.pk).update(campaign_ends_at=timezone.now())
            return provider_call(provider, model='gpt-4o-mini', messages=[], max_tokens=100)
        from ai_assistant.bots.chat_service import ChatUsageLimitError
        with self.assertRaises(ChatUsageLimitError):
            invoke(self.user)
        provider.assert_not_called()

    def test_ordinary_accounts_do_not_get_campaign_charges(self):
        self.call(Mock(return_value={'usage': {'prompt_tokens': 20, 'completion_tokens': 30}}))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.campaign_tokens, 0)

    def test_monitoring_budget_does_not_disable_entitlement(self):
        from io import StringIO
        from django.core.management import call_command
        self.activate()
        UserProfile.objects.filter(pk=self.profile.pk).update(campaign_tokens=1000)
        output = StringIO()
        with override_settings(AI_MODEL_PRICING={
            'gpt-4o-mini': {'input_per_million': 1_000_000, 'output_per_million': 1_000_000},
            'text-embedding-3-small': {'input_per_million': 1_000_000, 'output_per_million': 0},
        }):
            call_command('k1_report', stdout=output)
        self.assertIn('No automatic action taken', output.getvalue())
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.effective_plan, 'pro')


@override_settings(K1_CAMPAIGN_ENABLED=True, K1_CAMPAIGN_CODE='test-campaign')
class CampaignConcurrencyTests(TransactionTestCase):
    def test_separate_connections_share_inflight_allowance(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Event
        from django.db import close_old_connections
        from ai_assistant.bots.chat_service import ChatUsageLimitError

        user = User.objects.create_user('concurrent-campaign')
        UserProfile.objects.get_or_create(user=user)
        redeem(user, 'test-campaign')
        UserProfile.objects.filter(user=user).update(campaign_tokens=TOKEN_LIMIT - 600)
        started, finish = Event(), Event()

        def provider(**kwargs):
            started.set()
            if not finish.wait(10):
                raise TimeoutError('Test provider synchronization timed out')
            return {'usage': {'prompt_tokens': 20, 'completion_tokens': 30}}

        def first():
            close_old_connections()
            try:
                provider_call(provider, campaign_user=user, model='gpt-4o-mini',
                              messages=[{'role': 'user', 'content': 'Hello'}], max_tokens=100)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(first)
            try:
                self.assertTrue(started.wait(10))
                other = Mock()
                with self.assertRaises(ChatUsageLimitError):
                    provider_call(other, campaign_user=user, model='gpt-4o-mini',
                                  messages=[{'role': 'user', 'content': 'Hello'}], max_tokens=100)
                other.assert_not_called()
            finally:
                finish.set()
            pending.result(timeout=10)
        profile = UserProfile.objects.get(user=user)
        self.assertEqual(profile.campaign_tokens, TOKEN_LIMIT - 550)
        self.assertEqual(profile.campaign_reserved_tokens, 0)
