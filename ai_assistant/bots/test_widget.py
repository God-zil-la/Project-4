"""U3 boundaries, owner visibility, shared pipeline, and browser contract."""
import uuid
from unittest.mock import patch

import openai
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .chat_service import ChatServiceError, _resolve_conversation
from .models import Bot, ChatMessage, Conversation
from .widget_views import token_for


class WidgetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_user(username='widget-owner')
        self.owner.profile.complimentary_plan = 'pro'
        self.owner.profile.save()
        self.bot = Bot.objects.create(owner=self.owner, name='Public guide', personality='Ask one question first.', response_tone='friendly')
        self.api = APIClient()
        self.api.force_authenticate(self.owner)
        self.public = APIClient(enforce_csrf_checks=True)
        self.settings_url = reverse('bots:widget-settings-api', args=[self.bot.pk])

    def enable(self, bot=None):
        bot = bot or self.bot
        response = self.api.patch(reverse('bots:widget-settings-api', args=[bot.pk]), {'widget_enabled': True}, format='json')
        self.assertEqual(response.status_code, 200)
        bot.refresh_from_db()
        return bot

    def url(self, name, bot=None):
        return reverse('bots:' + name, args=[(bot or self.bot).widget_public_id])

    def session(self, bot=None):
        response = self.public.post(self.url('public-session', bot), {}, format='json')
        self.assertEqual(response.status_code, 200)
        return response.data['visitor_token']

    def message(self, token, bot=None, message='Hello'):
        return self.public.post(self.url('public-message', bot), {'visitor_token': token, 'message': message}, format='json')

    def test_defaults_and_uuid_activation_idempotence(self):
        self.assertFalse(self.bot.widget_enabled)
        self.assertIsNone(self.bot.widget_public_id)
        self.enable()
        public_id = self.bot.widget_public_id
        self.assertIsInstance(public_id, uuid.UUID)
        self.enable()
        self.assertEqual(self.bot.widget_public_id, public_id)
        data = self.api.get(self.settings_url).data
        self.assertIn(str(public_id), data['public_url'])
        self.assertIn('<iframe', data['embed_code'])
        self.assertNotIn('Token ', data['embed_code'])

    def test_only_effective_pro_can_activate_including_complimentary(self):
        for plan in ('free', 'premium'):
            self.owner.profile.complimentary_plan = plan if plan == 'premium' else ''
            self.owner.profile.plan = plan
            self.owner.profile.save()
            self.assertFalse(self.api.get(self.settings_url).data['allowed'])
            self.assertEqual(self.api.patch(self.settings_url, {'widget_enabled': True}, format='json').status_code, 403)
        self.bot.refresh_from_db()
        self.assertIsNone(self.bot.widget_public_id)

    def test_settings_require_owner_and_authentication(self):
        self.assertIn(APIClient().get(self.settings_url).status_code, (401, 403))
        other = User.objects.create_user(username='other')
        self.api.force_authenticate(other)
        self.assertEqual(self.api.get(self.settings_url).status_code, 404)
        self.assertEqual(self.api.patch(self.settings_url, {'widget_enabled': True}, format='json').status_code, 404)

    def test_settings_strict_payload_and_regular_bot_api_cannot_bypass(self):
        for value in ('true', 1, None, [], {}):
            self.assertEqual(self.api.patch(self.settings_url, {'widget_enabled': value}, format='json').status_code, 400)
        for body in ([], {}, {'widget_enabled': True, 'widget_public_id': str(uuid.uuid4())}):
            self.assertEqual(self.api.patch(self.settings_url, body, format='json').status_code, 400)
        self.api.patch(reverse('bots:bot-detail', args=[self.bot.pk]), {'widget_enabled': True}, format='json')
        self.bot.refresh_from_db()
        self.assertFalse(self.bot.widget_enabled)

    def test_public_routes_reject_internal_and_unknown_identifiers(self):
        self.assertEqual(self.public.get(f'/bots/public/{self.bot.pk}/').status_code, 404)
        self.assertEqual(self.public.get(reverse('bots:public-chat', args=[uuid.uuid4()])).status_code, 404)

    def test_disable_and_downgrade_block_all_public_access(self):
        self.enable()
        token = self.session()
        for change in ('disable', 'downgrade'):
            with self.subTest(change=change):
                if change == 'disable':
                    self.api.patch(self.settings_url, {'widget_enabled': False}, format='json')
                else:
                    Bot.objects.filter(pk=self.bot.pk).update(widget_enabled=True)
                    self.owner.profile.complimentary_plan = ''
                    self.owner.profile.save()
                self.assertEqual(self.public.get(self.url('public-chat')).status_code, 404)
                self.assertEqual(self.public.post(self.url('public-session'), {}, format='json').status_code, 404)
                self.assertEqual(self.message(token).status_code, 404)
        self.assertEqual(self.api.patch(self.settings_url, {'widget_enabled': False}, format='json').status_code, 200)

    def test_inactive_owner_blocks_public_access(self):
        self.enable()
        User.objects.filter(pk=self.owner.pk).update(is_active=False)
        self.assertEqual(self.public.get(self.url('public-chat')).status_code, 404)

    def test_visitors_have_distinct_conversations_and_owner_sees_them(self):
        self.enable()
        first, second = self.session(), self.session()
        self.assertNotEqual(first, second)
        conversations = Conversation.objects.filter(bot=self.bot, user=self.owner, is_widget=True)
        self.assertEqual(conversations.count(), 2)
        listing = self.api.get(reverse('bots:conversation-list-create'))
        self.assertEqual(len(listing.data), 2)
        self.assertTrue(all(row['is_widget'] for row in listing.data))
        for row in listing.data:
            detail = self.api.get(reverse('bots:conversation-detail', args=[row['conversation_id']]))
            self.assertEqual(detail.status_code, 200)
        self.assertNotIn('conversation_id', self.public.post(self.url('public-session'), {'visitor_token': first}, format='json').data)

    @patch('ai_assistant.bots.widget_views.process_bot_message')
    def test_tokens_cannot_cross_assistants_owners_or_use_conversation_uuid(self, process):
        self.enable()
        token = self.session()
        another = self.enable(Bot.objects.create(owner=self.owner, name='Second'))
        self.assertEqual(self.message(token, bot=another).status_code, 404)
        for invalid in (str(Conversation.objects.get().public_id), token + 'x', '', None, 12):
            self.assertEqual(self.message(invalid).status_code, 404)
        other = User.objects.create_user(username='new-owner')
        other.profile.complimentary_plan = 'pro'
        other.profile.save()
        Bot.objects.filter(pk=self.bot.pk).update(owner=other)
        self.assertEqual(self.message(token).status_code, 404)
        process.assert_not_called()

    def test_token_expiry_and_deleted_conversation(self):
        self.enable()
        with patch('django.core.signing.time.time', return_value=1):
            token = self.session()
        self.assertEqual(self.message(token).status_code, 404)
        token = self.session()
        Conversation.objects.all().delete()
        self.assertEqual(self.message(token).status_code, 404)

    def test_private_conversation_cannot_be_resumed_even_with_signed_payload(self):
        self.enable()
        private = Conversation.objects.create(bot=self.bot, user=self.owner)
        self.assertEqual(self.message(token_for(self.bot, private)).status_code, 404)

    def test_legacy_owner_chat_does_not_select_visitor_conversation(self):
        self.enable()
        self.session()
        visitor = Conversation.objects.get()
        own = _resolve_conversation(self.owner, self.bot)
        self.assertNotEqual(own.pk, visitor.pk)
        self.assertFalse(own.is_widget)
        with self.assertRaises(ChatServiceError):
            _resolve_conversation(self.owner, self.bot, visitor.public_id)
        self.client.force_login(self.owner)
        history = self.client.get(reverse('bots:bot_chat_api', args=[self.bot.pk])).json()
        self.assertEqual(history['conversation_id'], str(own.public_id))

    def test_web_settings_csrf_and_pro_gate(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        url = reverse('bots:widget-settings', args=[self.bot.pk])
        self.assertEqual(client.post(url, {'widget_enabled': 'on'}).status_code, 403)
        page = client.get(url)
        self.assertContains(page, 'Website Widget / Public Chatbot')
        csrf = client.cookies['csrftoken'].value
        self.assertEqual(client.post(url, {'widget_enabled': 'on', 'csrfmiddlewaretoken': csrf}).status_code, 302)
        self.owner.profile.complimentary_plan = ''
        self.owner.profile.save()
        self.assertEqual(client.post(url, {'widget_enabled': 'on', 'csrfmiddlewaretoken': csrf}).status_code, 403)

    def test_iframe_headers_escaping_and_no_owner_configuration_exposure(self):
        self.enable()
        Bot.objects.filter(pk=self.bot.pk).update(name='<script>alert(1)</script>')
        response = self.public.get(self.url('public-chat'))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('X-Frame-Options', response)
        self.assertIn("script-src 'self'", response['Content-Security-Policy'])
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, self.bot.personality)
        self.assertIn('no-store', response['Cache-Control'])
        self.assertEqual(response['X-Robots-Tag'], 'noindex, nofollow')
        self.client.force_login(self.owner)
        self.assertIn('X-Frame-Options', self.client.get(reverse('bots:widget-settings', args=[self.bot.pk])))

    @patch('ai_assistant.bots.widget_views.process_bot_message')
    def test_message_validation_before_pipeline(self, process):
        self.enable()
        token = self.session()
        for message in ('', '   ', 'x' * 4001, [], {}, None, 3):
            self.assertEqual(self.message(token, message=message).status_code, 400)
        self.assertEqual(self.public.post(self.url('public-message'), {'visitor_token': token, 'message': 'Hi', 'conversation_id': str(uuid.uuid4())}, format='json').status_code, 400)
        process.assert_not_called()

    def test_public_session_rate_limit_and_cache_failure_fail_closed(self):
        self.enable()
        for _ in range(30): self.session()
        response = self.public.post(self.url('public-session'), {}, format='json')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '60')
        with patch('ai_assistant.bots.widget_views.cache.add', side_effect=RuntimeError('offline')):
            self.assertEqual(self.public.post(self.url('public-session'), {}, format='json').status_code, 500)

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-only'})
    @patch('ai_assistant.bots.chat_service.openai.ChatCompletion.create')
    @patch('ai_assistant.bots.chat_service.search_relevant_chunks')
    def test_real_shared_pipeline_customization_rag_history_quota_and_visibility(self, search, answer):
        self.enable()
        first, second = self.session(), self.session()
        search.return_value = {'chunks': ['Approved knowledge content.'], 'tokens_used': 0, 'input_tokens': 0, 'output_tokens': 0, 'model': None}
        answer.return_value = openai.util.convert_to_openai_object({'choices': [{'message': {'content': 'A grounded answer.'}}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}, 'model': 'gpt-4o-mini'})
        self.assertEqual(self.message(first, message='Visitor one private question').data, {'response': 'A grounded answer.'})
        self.assertEqual(self.message(second, message='Visitor two question').status_code, 200)
        prompt = answer.call_args.kwargs['messages']
        self.assertNotIn('Visitor one private question', str(prompt))
        self.assertIn('Ask one question first.', prompt[0]['content'])
        self.assertIn('Approved knowledge content.', prompt[0]['content'])
        self.assertEqual(search.call_args.args[0], self.bot)
        self.assertEqual(self.message(first, message='Follow up').status_code, 200)
        prompt = answer.call_args.kwargs['messages']
        self.assertIn('Visitor one private question', str(prompt))
        self.assertNotIn('Visitor two question', str(prompt))
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.monthly_message_count, 3)
        self.assertEqual(ChatMessage.objects.filter(user=self.owner).count(), 6)
        history = self.public.post(self.url('public-session'), {'visitor_token': first}, format='json')
        self.assertEqual(len(history.data['messages']), 4)
        self.assertNotIn('plan', history.data)
        self.assertNotIn('monthly_messages_used', history.data)

    @patch('ai_assistant.bots.chat_service.get_ai_usage_status')
    def test_owner_quota_blocks_public_chat_without_exposing_financial_data(self, usage):
        self.enable()
        token = self.session()
        usage.return_value = {'allowed': False, 'monthly_message_limit_reached': True, 'monthly_cost_limit_reached': False}
        response = self.message(token)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(set(response.data), {'error'})
        self.assertFalse(ChatMessage.objects.exists())

    @patch('ai_assistant.bots.widget_views.process_bot_message', side_effect=RuntimeError('secret-provider-error'))
    def test_provider_failure_is_generic(self, process):
        self.enable()
        response = self.message(self.session())
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('secret-provider-error', str(response.data))

    def test_another_owner_cannot_read_visitor_history(self):
        self.enable()
        self.session()
        conversation = Conversation.objects.get()
        other = User.objects.create_user(username='foreign-reader')
        self.api.force_authenticate(other)
        self.assertEqual(self.api.get(reverse('bots:conversation-detail', args=[conversation.public_id])).status_code, 404)
        self.assertEqual(self.api.get(reverse('bots:conversation-list-create')).data, [])

    @patch('ai_assistant.bots.widget_views.process_bot_message')
    def test_browser_login_never_selects_logged_in_visitors_account(self, process):
        self.enable()
        visitor = User.objects.create_user(username='logged-in-visitor')
        self.public.force_login(visitor)
        token = self.session()
        process.return_value = {'response': 'Answer'}
        self.assertEqual(self.message(token).status_code, 200)
        args = process.call_args
        self.assertEqual(args.args[0], self.owner)
        self.assertEqual(args.kwargs['conversation'].user_id, self.owner.pk)

    @patch.dict('os.environ', {'OPENAI_API_KEY': 'test-only'})
    @patch('ai_assistant.bots.chat_service.openai.ChatCompletion.create', side_effect=RuntimeError('provider offline'))
    @patch('ai_assistant.bots.chat_service.search_relevant_chunks')
    def test_provider_failure_releases_quota_and_keeps_existing_history(self, search, answer):
        self.enable()
        token = self.session()
        search.return_value = {'chunks': [], 'tokens_used': 0, 'input_tokens': 0, 'output_tokens': 0, 'model': None}
        self.assertEqual(self.message(token).status_code, 503)
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.monthly_message_count, 0)
        self.assertEqual(ChatMessage.objects.count(), 0)
        self.assertEqual(Conversation.objects.count(), 1)
