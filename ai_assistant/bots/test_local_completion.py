from datetime import date, timedelta
from unittest.mock import patch
from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import IntegrityError
from django.test import TestCase, RequestFactory
from ai_assistant.accounts.models import UserProfile
from ai_assistant.bots.models import Bot, Conversation, ChatMessage, KnowledgeBase
from ai_assistant.bots.forms import KnowledgeBaseForm
from ai_assistant.bots.chat_service import _save_chat_exchange
from ai_assistant.bots.views import bot_chat_playground

class LocalCompletionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='local-check')
        self.bot = Bot.objects.create(owner=self.user, name='Local')

    def test_manual_only_form_and_empty_input(self):
        self.assertTrue(KnowledgeBaseForm(data={'manual_text':'Useful knowledge.'}).is_valid())
        self.assertFalse(KnowledgeBaseForm(data={'manual_text':'  '}).is_valid())

    def test_manual_only_upload_persists_without_file(self):
        request = RequestFactory().post('/', {'manual_text':'Useful knowledge.'})
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        request._dont_enforce_csrf_checks = True
        with patch('ai_assistant.bots.views.generate_embedding_batches', return_value=[[1.0]]) as batches:
            response = bot_chat_playground(request, self.bot.pk)
        self.assertEqual(response.status_code, 302)
        kb = KnowledgeBase.objects.get()
        self.assertFalse(kb.file)
        self.assertEqual(kb.chunks.get().text, 'Useful knowledge.')
        batches.assert_called_once()

    def test_stale_instances_do_not_lose_increments(self):
        first = UserProfile.objects.get(user=self.user)
        second = UserProfile.objects.get(user=self.user)
        first.increment_message_count()
        second.increment_message_count()
        first.refresh_from_db()
        self.assertEqual(first.daily_message_count, 2)

    def test_stale_reset_does_not_erase_new_day_usage(self):
        UserProfile.objects.filter(user=self.user).update(last_reset=date.today()-timedelta(days=1), daily_message_count=10)
        stale = UserProfile.objects.get(user=self.user)
        self.user.profile.increment_message_count()
        stale.reset_daily_count()
        self.assertEqual(stale.daily_message_count, 1)
        self.assertEqual(stale.last_reset, date.today())

    def test_partial_exchange_rolls_back(self):
        conversation = Conversation.objects.create(user=self.user, bot=self.bot)
        create = ChatMessage.objects.create
        def fail_assistant(**kwargs):
            if kwargs['sender'] == ChatMessage.SENDER_ASSISTANT:
                raise IntegrityError('Simulated failure')
            return create(**kwargs)
        with patch('ai_assistant.bots.chat_service.ChatMessage.objects.create', side_effect=fail_assistant):
            with self.assertRaises(IntegrityError):
                _save_chat_exchange(conversation, self.bot, self.user, 'Question', 'Answer')
        self.assertEqual(ChatMessage.objects.count(), 0)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.daily_message_count, 0)

    def test_counter_failure_rolls_back_exchange(self):
        conversation = Conversation.objects.create(user=self.user, bot=self.bot)
        with patch.object(UserProfile, 'increment_message_count', side_effect=IntegrityError('Counter failure')):
            with self.assertRaises(IntegrityError):
                _save_chat_exchange(conversation, self.bot, self.user, 'Question', 'Answer')
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_non_object_and_non_text_public_chat_input(self):
        self.user.profile.generate_api_key()
        for payload in [[], 'text', {'message': None}, {'message': {'nested': 'text'}}]:
            import json
            response = self.client.post('/accounts/api/public-chat/', json.dumps(payload),
                content_type='application/json', HTTP_X_API_KEY=self.user.profile.api_key)
            self.assertEqual(response.status_code, 400)

    def test_malformed_authenticated_api_input_has_no_side_effects(self):
        import json
        from django.core.cache import cache
        cache.clear()
        self.client.force_login(self.user)
        conversation = Conversation.objects.create(user=self.user, bot=self.bot, title='Original')
        cases = [('/bots/api/conversations/', 'post', []),
                 ('/bots/api/conversations/', 'post', {'bot_id':self.bot.pk,'title':None}),
                 (f'/bots/api/conversations/{conversation.public_id}/', 'patch', {'title':{}}),
                 (f'/bots/api/bot/{self.bot.pk}/chat/', 'post', []),
                 (f'/bots/api/bot/{self.bot.pk}/chat/', 'post', {'message':None}),
                 (f'/bots/api/bot/{self.bot.pk}/chat/', 'post', {'message':'Hello','conversation_id':{}})]
        with patch('ai_assistant.bots.api_views.process_bot_message') as process:
            for url, method, payload in cases:
                response = getattr(self.client, method)(url, json.dumps(payload), content_type='application/json')
                self.assertEqual(response.status_code, 400)
            process.assert_not_called()
        conversation.refresh_from_db()
        self.assertEqual(conversation.title, 'Original')
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(ChatMessage.objects.count(), 0)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.daily_message_count, 0)
