"""Customer API boundaries exercised without provider or network access."""
import importlib
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db import connection
from django.test import Client, TestCase, TransactionTestCase
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ai_assistant.bots.discord_auth import issue_discord_integration
from ai_assistant.bots.models import Bot, Conversation
from .api_keys import hash_api_key
from .models import UserProfile


class APIAccessTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('api-owner', password='test-password')
        self.other = User.objects.create_user('api-other')
        self.user.profile.plan = 'pro'
        self.user.profile.save(update_fields=['plan'])
        self.secret = self.user.profile.generate_api_key()
        self.bot = Bot.objects.create(owner=self.user, name='API assistant')
        self.foreign_bot = Bot.objects.create(owner=self.other, name='Private')
        self.api = APIClient()
        self.url = reverse('accounts:public-chat-api')
        self.manage = reverse('accounts:api-access')
        self.classifier = patch('ai_assistant.bots.chat_service.check_message_domain', return_value={
            'in_domain': False, 'rejection_message': 'Test response',
            'tokens_used': 0, 'input_tokens': 0, 'output_tokens': 0, 'model': 'test',
        })
        self.provider = self.classifier.start()
        self.addCleanup(self.classifier.stop)

    def chat(self, data=None, key=None):
        return self.api.post(self.url, data if data is not None else {
            'bot_id': self.bot.pk, 'message': 'Hello',
        }, format='json', HTTP_X_API_KEY=self.secret if key is None else key)

    def test_hash_storage_and_credential_boundaries(self):
        self.user.profile.refresh_from_db()
        digest = self.user.profile.api_key
        self.assertEqual(digest, hash_api_key(self.secret))
        self.assertEqual(self.chat().status_code, 200)
        for key in ('', digest, digest[7:], 'api_' + '0' * 64, 'x' * 10000):
            with self.subTest(key_type=len(key)):
                self.assertEqual(self.chat(key=key).status_code, 401)
        token = Token.objects.create(user=self.user)
        self.assertEqual(self.chat(key=token.key).status_code, 401)
        integration, discord_secret = issue_discord_integration(self.user, self.bot)
        self.assertEqual(self.chat(key=discord_secret).status_code, 401)
        self.assertEqual(self.api.post(reverse('bots:discord-api-bot-chat', args=[self.bot.pk]),
            {'message': 'hello'}, format='json', HTTP_AUTHORIZATION='Discord ' + self.secret).status_code, 401)

    def test_session_and_native_token_cannot_replace_api_key(self):
        self.api.force_login(self.user)
        self.assertEqual(self.chat(key='').status_code, 401)
        self.api.credentials(HTTP_AUTHORIZATION='Token ' + Token.objects.create(user=self.user).key)
        self.assertEqual(self.chat(key='').status_code, 401)

    def test_rotation_is_one_time_and_invalidates_old_key(self):
        self.client.force_login(self.user)
        get = self.client.get(self.manage)
        self.assertEqual(get.status_code, 200)
        self.assertNotContains(get, self.secret)
        response = self.client.post(self.manage, {'action': 'rotate'})
        self.assertEqual(response.status_code, 200)
        replacement = response.context['new_api_key']
        self.assertContains(response, replacement)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['Referrer-Policy'], 'no-referrer')
        self.assertEqual(self.chat().status_code, 401)
        self.assertEqual(self.chat(key=replacement).status_code, 200)
        self.assertNotContains(self.client.get(self.manage), replacement)

    def test_management_requires_login_and_csrf(self):
        self.assertEqual(self.client.get(self.manage).status_code, 302)
        browser = Client(enforce_csrf_checks=True)
        browser.force_login(self.user)
        self.assertEqual(browser.post(self.manage, {'action': 'rotate'}).status_code, 403)
        browser.get(self.manage)
        response = browser.post(self.manage, {'action': 'rotate'},
            HTTP_X_CSRFTOKEN=browser.cookies['csrftoken'].value)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(browser.get(self.manage + '?action=revoke').status_code, 200)
        self.assertEqual(self.chat(key=response.context['new_api_key']).status_code, 200)

    def test_downgrade_blocks_issue_and_chat_but_allows_revocation(self):
        self.client.force_login(self.user)
        for plan in ('premium', 'free'):
            UserProfile.objects.filter(user=self.user).update(plan=plan)
            self.assertEqual(self.chat().status_code, 403)
            self.assertEqual(self.client.post(self.manage, {'action': 'rotate'}).status_code, 403)
        self.provider.assert_not_called()
        self.assertEqual(self.client.post(self.manage, {'action': 'revoke'}).status_code, 200)
        UserProfile.objects.filter(user=self.user).update(plan='pro')
        self.assertEqual(self.chat().status_code, 401)

    def test_effective_complimentary_plan_and_inactive_account(self):
        UserProfile.objects.filter(user=self.user).update(plan='free', complimentary_plan='pro')
        self.assertEqual(self.chat().status_code, 200)
        User.objects.filter(pk=self.user.pk).update(is_active=False)
        self.assertEqual(self.chat().status_code, 401)

    def test_ownership_and_shape_validation_precede_provider_calls(self):
        self.assertEqual(self.chat({'bot_id': self.foreign_bot.pk, 'message': 'Hello'}).status_code, 404)
        for data in ([], 'text', {'bot_id': True, 'message': 'Hi'},
                     {'bot_id': {}, 'message': 'Hi'}, {'bot_id': self.bot.pk, 'message': []},
                     {'bot_id': self.bot.pk, 'message': ''},
                     {'bot_id': self.bot.pk, 'message': 'Hi', 'conversation_id': {}}):
            self.assertEqual(self.chat(data).status_code, 400)
        self.provider.assert_not_called()
        self.assertEqual(Conversation.objects.count(), 0)

    def test_new_conversation_continuation_and_foreign_conversation(self):
        private = Conversation.objects.create(user=self.user, bot=self.bot)
        first = self.chat()
        self.assertEqual(first.status_code, 200, first.data)
        cid = first.data['conversation_id']
        self.assertNotEqual(cid, str(private.public_id))
        second = self.chat({'bot_id': self.bot.pk, 'message': 'Again', 'conversation_id': cid})
        self.assertEqual(second.data['conversation_id'], cid)
        self.assertNotEqual(self.chat().data['conversation_id'], cid)
        foreign = Conversation.objects.create(user=self.other, bot=self.foreign_bot)
        for conversation_id in (str(foreign.public_id), 'invalid-uuid'):
            self.assertEqual(self.chat({'bot_id': self.bot.pk, 'message': 'Hi',
                'conversation_id': conversation_id}).status_code, 400)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.monthly_message_count, 3)

    def test_quota_and_rate_limit_create_no_conversations(self):
        UserProfile.objects.filter(user=self.user).update(monthly_message_count=10000)
        self.assertEqual(self.chat().status_code, 403)
        UserProfile.objects.filter(user=self.user).update(monthly_message_count=0)
        from ai_assistant.bots.chat_service import ChatRateLimitError
        with patch('ai_assistant.bots.chat_service._check_rate_limit',
                   side_effect=ChatRateLimitError('Too many requests.', 30)):
            response = self.chat()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.data['retry_after_seconds'], 30)
        self.assertEqual(Conversation.objects.count(), 0)
        self.provider.assert_not_called()

    def test_error_response_does_not_expose_secret(self):
        with patch('ai_assistant.accounts.api_views.process_bot_message',
                   side_effect=RuntimeError('secret-private-detail')):
            response = self.chat()
        self.assertEqual(response.status_code, 500)
        self.assertNotIn('secret-private-detail', str(response.data))
        self.assertIn('no-store', response['Cache-Control'])

    def test_discord_conversation_cannot_read_private_or_other_integration(self):
        integration, secret = issue_discord_integration(self.user, self.bot)
        another, _ = issue_discord_integration(self.user, self.bot)
        url = reverse('bots:discord-api-bot-chat', args=[self.bot.pk])
        def send(cid=None):
            payload = {'message': 'Hello'}
            if cid:
                payload['conversation_id'] = cid
            return self.api.post(url, payload, format='json', HTTP_AUTHORIZATION='Discord ' + secret)
        first = send()
        self.assertEqual(first.status_code, 200, first.data)
        cid = first.data['conversation_id']
        self.assertEqual(Conversation.objects.get(public_id=cid).discord_integration, integration)
        self.assertEqual(send(cid).status_code, 200)
        for scope in (None, another):
            private = Conversation.objects.create(user=self.user, bot=self.bot, discord_integration=scope)
            self.assertEqual(send(str(private.public_id)).status_code, 400)

    def test_revocation_is_independent_from_discord_and_login(self):
        integration, secret = issue_discord_integration(self.user, self.bot)
        token = Token.objects.create(user=self.user)
        self.client.force_login(self.user)
        self.client.post(self.manage, {'action': 'revoke'})
        self.assertEqual(self.chat().status_code, 401)
        self.assertEqual(self.api.post(reverse('bots:discord-api-bot-chat', args=[self.bot.pk]),
            {'message': 'Hello'}, format='json', HTTP_AUTHORIZATION='Discord ' + secret).status_code, 200)
        self.assertTrue(Token.objects.filter(key=token.key).exists())
        self.assertEqual(self.client.get(self.manage).status_code, 200)

    def test_migration_hashes_legacy_keys_without_breaking_clients(self):
        legacy = 'a' * 32
        UserProfile.objects.filter(user=self.user).update(api_key=legacy)
        module = importlib.import_module('ai_assistant.accounts.migrations.0012_hash_customer_api_keys')
    def test_implicit_private_chat_reuses_private_history_after_discord_activity(self):
        private = Conversation.objects.create(user=self.user, bot=self.bot)
        integration, secret = issue_discord_integration(self.user, self.bot)
        discord_url = reverse('bots:discord-api-bot-chat', args=[self.bot.pk])
        discord = self.api.post(discord_url, {'message': 'Discord channel text'},
            format='json', HTTP_AUTHORIZATION='Discord ' + secret)
        self.assertEqual(discord.status_code, 200, discord.data)
        discord_history = Conversation.objects.get(public_id=discord.data['conversation_id'])
        from ai_assistant.bots.models import ChatMessage
        before = list(ChatMessage.objects.filter(conversation=discord_history).values())
        self.api.force_authenticate(user=self.user)
        response = self.api.post(reverse('bots:api-bot-chat', args=[self.bot.pk]),
            {'message': 'Private text'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['conversation_id'], str(private.public_id))
        self.assertTrue(ChatMessage.objects.filter(conversation=private, message='Private text').exists())
        self.assertEqual(list(ChatMessage.objects.filter(conversation=discord_history).values()), before)

    def test_implicit_private_chat_creates_private_history_when_only_discord_exists(self):
        integration, secret = issue_discord_integration(self.user, self.bot)
        discord_url = reverse('bots:discord-api-bot-chat', args=[self.bot.pk])
        histories = []
        for message in ('Discord channel text', 'Discord DM text'):
            response = self.api.post(discord_url, {'message': message},
                format='json', HTTP_AUTHORIZATION='Discord ' + secret)
            self.assertEqual(response.status_code, 200, response.data)
            histories.append(response.data['conversation_id'])
        self.api.force_authenticate(user=self.user)
        response = self.api.post(reverse('bots:api-bot-chat', args=[self.bot.pk]),
            {'message': 'Private text'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        private_id = response.data['conversation_id']
        self.assertNotIn(private_id, histories)
        self.assertIsNone(Conversation.objects.get(public_id=private_id).discord_integration_id)
        self.api.force_authenticate(user=None)
        for cid in histories:
            response = self.api.post(discord_url, {'message': 'Continue', 'conversation_id': cid},
                format='json', HTTP_AUTHORIZATION='Discord ' + secret)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data['conversation_id'], cid)
        response = self.api.post(discord_url, {'message': 'Read private', 'conversation_id': private_id},
            format='json', HTTP_AUTHORIZATION='Discord ' + secret)
        self.assertEqual(response.status_code, 400)

        module.hash_existing_keys(apps, SimpleNamespace(connection=connection))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.api_key, hash_api_key(legacy))
        self.assertEqual(self.chat(key=legacy).status_code, 200)
        self.assertEqual(self.chat(key=self.user.profile.api_key).status_code, 401)


class APIKeyMigrationTests(TransactionTestCase):
    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_key_survives_upgrade_and_is_revoked_on_rollback(self):
        before = [('accounts', '0011_unique_username_case_insensitive')]
        after = [('accounts', '0012_hash_customer_api_keys')]
        historical = self.migrate(before)
        user = historical.get_model('auth', 'User').objects.create(username='legacy-api')
        legacy = 'b' * 32
        profile = historical.get_model('accounts', 'UserProfile').objects.create(user=user, api_key=legacy)
        upgraded = self.migrate(after)
        Profile = upgraded.get_model('accounts', 'UserProfile')
        self.assertEqual(Profile.objects.get(pk=profile.pk).api_key, hash_api_key(legacy))
        rolled_back = self.migrate(before)
        replacement = rolled_back.get_model('accounts', 'UserProfile').objects.get(pk=profile.pk).api_key
        self.assertEqual(len(replacement), 64)
        self.assertNotEqual(replacement, legacy)
        self.assertNotEqual(replacement, hash_api_key(legacy))
        self.migrate(after)
        self.assertEqual(Profile.objects.get(pk=profile.pk).api_key, hash_api_key(replacement))
