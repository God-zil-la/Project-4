from unittest.mock import patch
import openai
from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from ai_assistant.bots.models import Bot, KnowledgeBase, KnowledgeChunk, Conversation, ChatMessage
from ai_assistant.bots.knowledge_utils import search_relevant_chunks, check_message_domain, CATEGORY_DOMAIN_RULES
from ai_assistant.bots.chat_service import process_bot_message, ChatServiceError
from ai_assistant.dashboard.models import BotUsageLog
from ai_assistant.dashboard.cost_utils import calculate_user_current_month_cost

@patch.dict('os.environ', {'OPENAI_API_KEY': 'test-only'})
class AIQualityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='quality')
        self.bot = Bot.objects.create(owner=self.user, name='Quality', category='general')

    def completion(self):
        return openai.util.convert_to_openai_object({
            'choices': [{'message': {'content': 'A grounded answer.'}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15},
            'model': 'gpt-4o-mini'})

    def test_all_categories_have_rules(self):
        self.assertFalse(set(dict(Bot.CATEGORY_CHOICES)) - set(CATEGORY_DOMAIN_RULES))

    @patch('ai_assistant.bots.knowledge_utils.openai.ChatCompletion.create')
    def test_general_bypasses_classifier(self, api):
        self.assertTrue(check_message_domain(self.bot, 'Hello')['in_domain'])
        api.assert_not_called()

    @patch('ai_assistant.bots.chat_service.check_message_domain')
    @patch('ai_assistant.bots.chat_service.search_relevant_chunks')
    @patch('ai_assistant.bots.chat_service.openai.ChatCompletion.create')
    def test_rejected_category_never_retrieves_or_answers(self, answer, search, domain):
        domain.return_value = dict(in_domain=False, tokens_used=4, input_tokens=3,
                                   output_tokens=1, model='gpt-4o-mini')
        result = process_bot_message(self.user, self.bot, 'Unrelated request')
        self.assertFalse(result['in_domain'])
        search.assert_not_called()
        answer.assert_not_called()
        self.assertEqual(BotUsageLog.objects.get().tokens_used, 4)
        self.assertEqual(ChatMessage.objects.count(), 2)

    @patch('ai_assistant.bots.chat_service.openai.ChatCompletion.create')
    def test_no_knowledge_chat_tracks_alias_cost(self, api):
        api.return_value = self.completion()
        result = process_bot_message(self.user, self.bot, 'Hello')
        self.assertEqual(result['tokens_used'], 15)
        self.assertGreater(calculate_user_current_month_cost(self.user)['cost_usd'], 0)
        self.assertEqual(ChatMessage.objects.count(), 2)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.daily_message_count, 1)

    @patch('ai_assistant.bots.chat_service.search_relevant_chunks', side_effect=RuntimeError('secret'))
    @patch('ai_assistant.bots.chat_service.openai.ChatCompletion.create')
    def test_retrieval_failure_falls_back(self, api, search):
        api.return_value = self.completion()
        self.assertEqual(process_bot_message(self.user, self.bot, 'Hello')['response'], 'A grounded answer.')
        self.assertIn('[No relevant knowledge found.]', api.call_args.kwargs['messages'][0]['content'])

    @patch('ai_assistant.bots.knowledge_utils.generate_embedding', return_value=[1.0, 0.0])
    def test_retrieval_excludes_other_bots_and_bad_vectors(self, embedding):
        other = Bot.objects.create(owner=self.user, name='Other')
        for bot, text, vector in [(self.bot, 'Relevant', [1.0, 0.0]),
                                  (self.bot, 'Unrelated', [-1.0, 0.0]),
                                  (self.bot, 'Invalid', [1.0]),
                                  (other, 'Other private content', [1.0, 0.0])]:
            kb = KnowledgeBase.objects.create(bot=bot, uploaded_by=self.user)
            KnowledgeChunk.objects.create(knowledge_file=kb, text=text, embedding=vector)
        self.assertEqual(search_relevant_chunks(self.bot, 'Query'), ['Relevant'])

    def test_foreign_conversation_rejected(self):
        other = User.objects.create_user(username='foreign')
        conversation = Conversation.objects.create(user=other, bot=self.bot)
        with self.assertRaises(ChatServiceError):
            process_bot_message(self.user, self.bot, 'Hello', conversation=conversation.public_id)
        self.assertEqual(ChatMessage.objects.count(), 0)
