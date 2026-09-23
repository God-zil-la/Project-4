"""Native parity adapters must preserve the web's data and authorization."""
import json
import tempfile
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.authtoken.models import Token
from .models import Bot, ChatMessage, KnowledgeBase, KnowledgeChunk


class ParityAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('native-owner', password='test-secret')
        self.other = User.objects.create_user('other-owner', password='test-secret')
        self.bot = Bot.objects.create(owner=self.user, name='My assistant')
        self.foreign_bot = Bot.objects.create(owner=self.other, name='Private assistant')
        self.client = APIClient()
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        self.url = f'/bots/api/bots/{self.bot.id}/knowledge/'
        self.media = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.media.cleanup)
        self.addCleanup(self.settings_override.disable)

    def document(self, name='facts.txt', content=b'A useful fact about our products.'):
        return SimpleUploadedFile(name, content, content_type='text/plain')

    def test_endpoints_require_authentication(self):
        anonymous = APIClient()
        for url in ['/bots/api/dashboard/', '/bots/api/analytics/', self.url]:
            self.assertEqual(anonymous.get(url).status_code, 401)
        self.assertEqual(anonymous.post(self.url, {'file': self.document()}).status_code, 401)

    def test_dashboard_is_exact_web_context_and_effective_plan(self):
        profile = self.user.profile
        profile.complimentary_plan = 'pro'
        profile.save()
        self.client.force_login(self.user)
        web = self.client.get('/dashboard/')
        native = self.client.get('/bots/api/dashboard/')
        self.assertEqual(native.status_code, 200)
        for key, value in native.data.items():
            self.assertEqual(value, web.context[key])
        self.assertEqual(native.data['current_plan'], 'pro')
        self.assertEqual(native.data['bot_limit'], 15)

    def test_analytics_exact_web_counts_and_owner_isolation(self):
        ChatMessage.objects.create(bot=self.bot, user=self.user, sender='user', message='Hello')
        ChatMessage.objects.create(bot=self.bot, user=self.user, sender='bot', message='Hi')
        ChatMessage.objects.create(bot=self.foreign_bot, user=self.other, sender='user', message='Private')
        self.client.force_login(self.user)
        web = self.client.get('/bots/analytics/')
        native = self.client.get('/bots/api/analytics/')
        self.assertEqual(native.status_code, 200)
        self.assertEqual(native.data['bot_data'], json.loads(web.context['bot_data']))
        self.assertEqual(native.data['time_data'], json.loads(web.context['time_data']))
        self.assertEqual(native.data['bot_data']['counts'], [2])
        self.assertEqual(sum(native.data['time_data']['counts']), 2)

    def test_owner_isolation_for_all_knowledge_operations(self):
        foreign = KnowledgeBase.objects.create(bot=self.foreign_bot, uploaded_by=self.other)
        foreign_url = f'/bots/api/bots/{self.foreign_bot.id}/knowledge/'
        self.assertEqual(self.client.get(foreign_url).status_code, 404)
        self.assertEqual(self.client.post(foreign_url, {'file': self.document()}).status_code, 404)
        self.assertEqual(self.client.delete(f'{foreign_url}{foreign.id}/').status_code, 404)
        self.assertEqual(self.client.delete(f'{self.url}{foreign.id}/').status_code, 404)
        self.assertTrue(KnowledgeBase.objects.filter(pk=foreign.id).exists())

    @patch('ai_assistant.bots.knowledge_service.generate_embedding_batches', return_value=[[0.1, 0.2]])
    def test_upload_list_delete_existing_pipeline(self, embeddings):
        response = self.client.post(self.url, {'file': self.document()}, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        item = KnowledgeBase.objects.get(pk=response.data['id'])
        self.assertEqual(item.uploaded_by, self.user)
        self.assertEqual(item.source_size_bytes, len(b'A useful fact about our products.'))
        self.assertEqual(item.chunks.count(), 1)
        self.assertEqual(self.client.get(self.url).data['files'][0]['id'], item.id)
        self.assertEqual(self.client.delete(f'{self.url}{item.id}/').status_code, 204)
        self.assertFalse(KnowledgeChunk.objects.exists())

    @patch('ai_assistant.bots.knowledge_service.generate_embedding_batches')
    def test_invalid_type_empty_file_and_missing_file_do_not_embed(self, embeddings):
        for data in [{'file': self.document('photo.png')}, {'file': self.document(content=b'')}, {}, {'manual_text': 'No new native editor'}]:
            self.assertEqual(self.client.post(self.url, data, format='multipart').status_code, 400)
        embeddings.assert_not_called()

    @patch('ai_assistant.bots.knowledge_service.generate_embedding_batches')
    def test_quota_uses_effective_plan_and_blocks_before_embedding(self, embeddings):
        KnowledgeBase.objects.create(bot=self.bot, source_size_bytes=10*1024*1024)
        response = self.client.post(self.url, {'file': self.document()}, format='multipart')
        self.assertEqual(response.status_code, 403)
        embeddings.assert_not_called()

    @patch('ai_assistant.bots.knowledge_service.generate_embedding_batches', side_effect=RuntimeError('upstream failure'))
    def test_processing_failure_does_not_create_knowledge(self, embeddings):
        response = self.client.post(self.url, {'file': self.document()}, format='multipart')
        self.assertEqual(response.status_code, 503)
        self.assertNotIn('upstream failure', str(response.data))
        self.assertFalse(KnowledgeBase.objects.exists())

    def test_duplicate_assistant_name_returns_validation_error(self):
        response = self.client.post('/bots/api/bots/', {'name': self.bot.name}, format='json')
        self.assertEqual(response.status_code, 400, response.data)

    def test_bot_creation_date_is_read_only(self):
        response = self.client.patch(f'/bots/api/bots/{self.bot.id}/', {'created_at': '2000-01-01T00:00:00Z'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['created_at'].startswith('2000'))

    def test_invalid_and_inactive_tokens_are_rejected_including_delete(self):
        urls = ['/accounts/api/me/', '/bots/api/dashboard/', '/bots/api/analytics/', self.url]
        self.client.credentials(HTTP_AUTHORIZATION='Token invalid-token')
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 401)
        self.assertEqual(self.client.delete(f'{self.url}1/').status_code, 401)
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        token = Token.objects.get(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 401)

    def test_session_upload_requires_csrf(self):
        browser = APIClient(enforce_csrf_checks=True)
        browser.force_login(self.user)
        self.assertEqual(browser.post(self.url, {'file': self.document()}).status_code, 403)

    def test_me_and_dashboard_reload_effective_plan_after_state_changes(self):
        from datetime import timedelta
        from django.utils import timezone
        profile = self.user.profile
        states = [
            ('free', '', None, 'free'),
            ('premium', 'active', None, 'premium'),
            ('pro', 'active', timezone.now() + timedelta(days=1), 'pro'),
            ('pro', 'past_due', None, 'free'),
            ('pro', 'active', timezone.now() - timedelta(seconds=1), 'free'),
        ]
        for plan, status, end, expected in states:
            with self.subTest(plan=plan, status=status, end=end):
                profile.plan = plan
                profile.stripe_subscription_id = 'sub_test' if status else ''
                profile.stripe_subscription_status = status
                profile.subscription_ends_at = end
                profile.save()
                self.assertEqual(self.client.get('/accounts/api/me/').data['plan'], expected)
                self.assertEqual(self.client.get('/bots/api/dashboard/').data['current_plan'], expected)
        profile.complimentary_plan = 'premium'
        profile.save()
        self.assertEqual(self.client.get('/accounts/api/me/').data['plan'], 'premium')

    @patch('ai_assistant.bots.knowledge_service.generate_embedding_batches', return_value=[[0.1]])
    @patch('ai_assistant.bots.knowledge_service.KnowledgeChunk.objects.create', side_effect=RuntimeError('database failure'))
    def test_chunk_failure_rolls_back_rows_and_stored_file(self, create, embeddings):
        from pathlib import Path
        response = self.client.post(self.url, {'file': self.document()}, format='multipart')
        self.assertEqual(response.status_code, 503)
        self.assertFalse(KnowledgeBase.objects.exists())
        self.assertFalse(KnowledgeChunk.objects.exists())
        self.assertFalse([p for p in Path(self.media.name).rglob('*') if p.is_file()])
