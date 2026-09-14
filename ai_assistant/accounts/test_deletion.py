import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from rest_framework.authtoken.models import Token

from ai_assistant.bots.models import (
    Bot, BotUsageLog, ChatMessage, Conversation, KnowledgeBase, KnowledgeChunk,
)
from ai_assistant.dashboard.models import BotUsageLog as DashboardUsage
from ai_assistant.payments.models import (
    BillingEmail, CheckoutAttempt, StripeEvent, SubscriptionChange, SubscriptionRecovery,
)
from .deletion import delete_account
from .models import DeletionFollowUp, FileDeletionJob, UserProfile

User = get_user_model()


class AccountDeletionTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.media = override_settings(MEDIA_ROOT=self.temp.name)
        self.media.enable()
        self.addCleanup(self.media.disable)
        self.user = User.objects.create_user('delete-me', 'owner@example.com', 'correct-password')
        self.other = User.objects.create_user('keep-me', 'other@example.com', 'other-password')
        self.url = reverse('accounts:delete_account')
        self.client.force_login(self.user)

    def submit(self, **extra):
        return self.client.post(self.url, {'password': 'correct-password', 'confirm': 'on', **extra})

    def upload(self, owner=None, uploader=None):
        bot = Bot.objects.create(owner=owner or self.user, name=f'bot-{Bot.objects.count()}')
        kb = KnowledgeBase.objects.create(bot=bot, uploaded_by=uploader or self.user,
            file=SimpleUploadedFile('private.txt', b'private knowledge'))
        KnowledgeChunk.objects.create(knowledge_file=kb, text='private knowledge', embedding=[0.1])
        return bot, kb

    def provider(self, subscriptions=None, sessions=None, schedules=None):
        self.user.profile.stripe_customer_id = 'cus_owner'
        self.user.profile.save()
        mocks = {}
        for name, entries in [('Subscription.list', subscriptions or []),
                              ('checkout.Session.list', sessions or []),
                              ('SubscriptionSchedule.list', schedules or [])]:
            p = patch('ai_assistant.accounts.deletion.stripe.' + name)
            mocks[name] = p.start()
            self.addCleanup(p.stop)
            mocks[name].return_value.auto_paging_iter.return_value = entries
        return mocks

    def test_public_pages_get_and_head_without_login(self):
        client = Client()
        for url, text in [('/privacy/', 'Privacy Policy'), ('/delete-account/', 'Delete your AI Assistant account')]:
            with self.subTest(url=url):
                response = client.get(url)
                self.assertContains(response, text)
                self.assertContains(response, 'support@myaiassistantapp.se')
                self.assertContains(response, 'name="viewport"')
                self.assertContains(response, 'href="/delete-account/"')
                self.assertEqual(client.head(url).status_code, 200)

    def test_confirmation_requires_login_and_get_is_non_destructive(self):
        self.assertEqual(Client().get(self.url).status_code, 302)
        self.assertEqual(Client().post(self.url).status_code, 302)
        self.assertContains(self.client.get(self.url), 'Current password')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertEqual(self.client.delete(self.url).status_code, 405)

    @override_settings(DEBUG=False, SECURE_SSL_REDIRECT=True)
    def test_public_pages_remain_public_over_production_https(self):
        for url in ['/privacy/', '/delete-account/']:
            self.assertEqual(Client().get(url, secure=True).status_code, 200)

    def test_dashboard_links_to_confirmation(self):
        self.assertContains(self.client.get('/dashboard/'), f'href="{self.url}"')

    def test_wrong_password_and_missing_confirmation_preserve_account(self):
        self.assertContains(self.submit(password='wrong'), 'password was not accepted')
        self.assertContains(self.submit(confirm=''), 'This field is required')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(DeletionFollowUp.objects.exists())

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, {'password': 'correct-password', 'confirm': 'on'}).status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_cascades_uploads_outbox_tokens_and_other_account_isolation(self):
        bot, kb = self.upload()
        filename = kb.file.path
        other_bot, other_kb = self.upload(owner=self.other, uploader=self.other)
        other_filename = other_kb.file.path
        # SET_NULL uploader relation must also be handled, even on another bot.
        cross_kb = KnowledgeBase.objects.create(bot=other_bot, uploaded_by=self.user,
            file=SimpleUploadedFile('cross.txt', b'my upload'))
        cross_name = cross_kb.file.path
        conversation = Conversation.objects.create(user=self.user, bot=bot)
        ChatMessage.objects.create(user=self.user, bot=bot, conversation=conversation, sender='user', message='secret')
        ChatMessage.objects.create(user=self.user, bot=other_bot, sender='assistant', message='legacy')
        other_conversation = Conversation.objects.create(user=self.other, bot=other_bot)
        BotUsageLog.objects.create(user=self.user, bot=bot, tokens_used=2)
        DashboardUsage.objects.create(user=self.user, bot=bot, tokens_used=2)
        Token.objects.create(user=self.user)
        key = self.user.profile.api_key
        BillingEmail.objects.create(key='mine', recipient='OWNER@example.com', subject='bill', body='private')
        BillingEmail.objects.create(key='other', recipient=self.other.email, subject='keep', body='keep')
        StripeEvent.objects.create(event_id='evt_keep_for_deduplication')
        cache.set(f'ai-rate-limit:{self.user.pk}', 1, 60)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.submit(user_id=self.other.pk)
        self.assertRedirects(response, '/delete-account/')
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(UserProfile.objects.filter(user_id=self.user.pk).exists())
        self.assertFalse(Token.objects.exists())
        self.assertFalse(ChatMessage.objects.exists())
        self.assertFalse(BotUsageLog.objects.exists())
        self.assertFalse(DashboardUsage.objects.exists())
        self.assertFalse(Path(filename).exists())
        self.assertFalse(Path(cross_name).exists())
        self.assertTrue(Path(other_filename).exists())
        self.assertEqual(list(Bot.objects.values_list('pk', flat=True)), [other_bot.pk])
        self.assertEqual(list(Conversation.objects.values_list('pk', flat=True)), [other_conversation.pk])
        self.assertEqual(KnowledgeBase.objects.count(), 1)
        self.assertEqual(KnowledgeChunk.objects.count(), 1)
        self.assertEqual(BillingEmail.objects.get().key, 'other')
        self.assertEqual(StripeEvent.objects.count(), 1)
        self.assertEqual(DeletionFollowUp.objects.get().email, self.user.email)
        self.assertFalse(FileDeletionJob.objects.exists())
        self.assertIsNone(cache.get(f'ai-rate-limit:{self.user.pk}'))
        self.assertNotIn('_auth_user_id', self.client.session)
        response = Client().post('/accounts/api/public-chat/', {}, HTTP_X_API_KEY=key)
        self.assertEqual(response.status_code, 401)

    def test_old_signed_cookie_no_longer_authenticates(self):
        old_device = Client()
        old_device.force_login(self.user)
        self.submit()
        self.assertEqual(old_device.get('/dashboard/').status_code, 302)

    def test_transaction_failure_does_not_delete_files_or_user(self):
        _, kb = self.upload()
        with self.captureOnCommitCallbacks(execute=True):
            with self.assertRaises(RuntimeError), transaction.atomic():
                delete_account(self.user.pk, password='correct-password')
                raise RuntimeError('rollback')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertTrue(Path(kb.file.path).exists())
        self.assertTrue(KnowledgeBase.objects.filter(pk=kb.pk).exists())
        self.assertFalse(FileDeletionJob.objects.exists())
        self.assertFalse(DeletionFollowUp.objects.exists())

    def test_storage_failure_is_durable_and_retry_removes_file(self):
        _, kb = self.upload()
        storage = KnowledgeBase._meta.get_field('file').storage
        with patch.object(storage, 'delete', side_effect=OSError('offline')):
            with self.captureOnCommitCallbacks(execute=True):
                response = self.submit()
            self.assertEqual(response.status_code, 302)
            self.assertEqual(FileDeletionJob.objects.count(), 1)
            with self.assertRaises(CommandError):
                call_command('retry_file_deletions', stdout=StringIO())
        self.assertTrue(Path(kb.file.path).exists())
        call_command('retry_file_deletions', stdout=StringIO())
        self.assertFalse(Path(kb.file.path).exists())
        self.assertFalse(FileDeletionJob.objects.exists())

    def test_bot_cascade_also_removes_file_after_commit(self):
        bot, kb = self.upload()
        with self.captureOnCommitCallbacks(execute=True):
            bot.delete()
        self.assertFalse(Path(kb.file.path).exists())

    def test_direct_orm_user_deletion_cannot_skip_extra_cleanup(self):
        _, kb = self.upload(owner=self.other)
        BillingEmail.objects.create(key='direct', recipient=self.user.email, subject='bill', body='private')
        with self.captureOnCommitCallbacks(execute=True):
            User.objects.filter(pk=self.user.pk).delete()
        self.assertFalse(Path(kb.file.path).exists())
        self.assertFalse(KnowledgeBase.objects.filter(pk=kb.pk).exists())
        self.assertFalse(BillingEmail.objects.exists())
        self.assertEqual(DeletionFollowUp.objects.count(), 1)

    def test_individual_knowledge_delete_queues_storage_cleanup(self):
        bot, kb = self.upload()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse('bots:delete-knowledge', args=[bot.pk, kb.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Path(kb.file.path).exists())

    def test_shared_file_is_preserved_until_last_reference_deleted(self):
        _, kb = self.upload()
        other_bot = Bot.objects.create(owner=self.other, name='shared')
        shared = KnowledgeBase.objects.create(bot=other_bot, uploaded_by=self.other, file=kb.file.name)
        with self.captureOnCommitCallbacks(execute=True):
            self.submit()
        self.assertTrue(Path(kb.file.path).exists())
        with self.captureOnCommitCallbacks(execute=True):
            shared.delete()
        self.assertFalse(Path(kb.file.path).exists())

    def test_active_or_scheduled_cancellation_blocks_deletion(self):
        self.provider(subscriptions=[{'id':'sub_1', 'customer':'cus_owner', 'livemode':False,
                                      'status':'active', 'cancel_at_period_end':True}])
        self.assertContains(self.submit(), 'Billing needs to be resolved')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(DeletionFollowUp.objects.exists())

    def test_canceled_subscription_and_completed_local_billing_records_are_deleted(self):
        self.provider(subscriptions=[{'id':'sub_1', 'customer':'cus_owner', 'livemode':False, 'status':'canceled'}],
                      sessions=[{'id':'cs_1', 'status':'complete'}])
        profile = self.user.profile
        profile.stripe_subscription_id = 'sub_1'
        profile.save()
        CheckoutAttempt.objects.create(profile=profile, plan='pro', session_id='cs_1', success_url='/', cancel_url='/')
        SubscriptionChange.objects.create(profile=profile, action='upgrade', status='complete')
        SubscriptionRecovery.objects.create(profile=profile, source_subscription='sub_1', completed=True)
        self.assertEqual(self.submit().status_code, 302)
        for model in [CheckoutAttempt, SubscriptionChange, SubscriptionRecovery]:
            self.assertFalse(model.objects.exists())
        self.assertEqual(DeletionFollowUp.objects.get().stripe_customer_id, 'cus_owner')

    def test_provider_failure_fails_closed_without_exposing_error(self):
        mocks = self.provider()
        mocks['Subscription.list'].side_effect = RuntimeError('SECRET provider details')
        response = self.submit()
        self.assertContains(response, 'could not verify billing')
        self.assertNotContains(response, 'SECRET')
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_open_checkout_blocks_deletion(self):
        self.provider(sessions=[{'id':'cs_open', 'status':'open'}])
        self.assertContains(self.submit(), 'Billing needs to be resolved')

    def test_future_schedule_blocks_deletion(self):
        self.provider(schedules=[{'id':'sched', 'status':'not_started'}])
        self.assertContains(self.submit(), 'Billing needs to be resolved')

    def test_unfinished_recovery_blocks_without_provider_call(self):
        SubscriptionRecovery.objects.create(profile=self.user.profile, source_subscription='sub_pending')
        self.assertContains(self.submit(), 'Billing needs to be resolved')

    def test_paid_account_without_provider_link_blocks(self):
        self.user.profile.plan = 'pro'
        self.user.profile.save()
        self.assertContains(self.submit(), 'Billing needs to be resolved')

    def test_support_command_requires_verified_owner_and_matching_email(self):
        with self.assertRaises(CommandError):
            call_command('delete_ai_account', user_id=self.user.pk, confirm_email=self.user.email, stdout=StringIO())
        with self.assertRaises(CommandError):
            call_command('delete_ai_account', user_id=self.user.pk, confirm_email=self.other.email,
                         ownership_verified=True, stdout=StringIO())
        call_command('delete_ai_account', user_id=self.user.pk, confirm_email=self.user.email,
                     ownership_verified=True, stdout=StringIO())
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())

    def test_followup_is_purged_only_after_provider_review(self):
        self.submit()
        followup = DeletionFollowUp.objects.get()
        with self.assertRaises(CommandError):
            call_command('complete_deletion_followup', id=followup.pk, stdout=StringIO())
        call_command('complete_deletion_followup', id=followup.pk, provider_review_complete=True, stdout=StringIO())
        self.assertFalse(DeletionFollowUp.objects.exists())
