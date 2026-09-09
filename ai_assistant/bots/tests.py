from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from ai_assistant.bots.models import Bot, KnowledgeBase, KnowledgeChunk
from ai_assistant.bots.views import bot_chat_playground
from ai_assistant.dashboard.models import BotUsageLog


class KnowledgeUploadTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.settings_override = self.settings(MEDIA_ROOT=self.media.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = User.objects.create_user(username='upload-owner')
        self.bot = Bot.objects.create(owner=self.user, name='Upload bot')
        self.existing = KnowledgeBase.objects.create(bot=self.bot, uploaded_by=self.user)
        KnowledgeChunk.objects.create(
            knowledge_file=self.existing, text='Existing knowledge', embedding=[1.0]
        )
        self.result = dict(embedding=[0.5], tokens_used=3, input_tokens=3,
                           output_tokens=0, model='text-embedding-3-small')

    def upload(self, results=None):
        request = RequestFactory().post('/', {
            'file': SimpleUploadedFile('knowledge.txt', b'First. Second.')
        })
        request.user = self.user
        request._dont_enforce_csrf_checks = True
        request.session = {}
        request._messages = FallbackStorage(request)
        with patch('ai_assistant.bots.views.chunk_text', return_value=['First.', 'Second.']), \
             patch('ai_assistant.bots.views.generate_embedding',
                   side_effect=results or [self.result, self.result]), \
             patch('ai_assistant.bots.views.render', return_value=HttpResponse()):
            response = bot_chat_playground(request, self.bot.pk)
        self.assertIn(response.status_code, (200, 302))
        return response, [str(message) for message in request._messages]

    def assert_no_partial_upload(self):
        self.assertEqual(KnowledgeBase.objects.count(), 1)
        self.assertEqual(KnowledgeChunk.objects.count(), 1)
        self.assertEqual(self.existing.chunks.get().text, 'Existing knowledge')
        self.assertFalse(any(p.is_file() for p in Path(self.media.name).rglob('*')))

    def test_success_saves_all_chunks_file_and_usage(self):
        response, messages = self.upload()
        self.assertEqual(response.status_code, 302)
        kb = KnowledgeBase.objects.exclude(pk=self.existing.pk).get()
        self.assertEqual(list(kb.chunks.values_list('text', flat=True)), ['First.', 'Second.'])
        with kb.file.open('rb') as uploaded:
            self.assertEqual(uploaded.read(), b'First. Second.')
        self.assertEqual(BotUsageLog.objects.count(), 2)
        self.assertIn('Knowledge uploaded and processed successfully!', messages)

    def test_later_embedding_failure_leaves_existing_knowledge(self):
        _, messages = self.upload([self.result, RuntimeError('Embedding failed')])
        self.assert_no_partial_upload()
        self.assertEqual(BotUsageLog.objects.count(), 1)
        self.assertTrue(any('Failed to process file' in message for message in messages))

    def test_empty_embedding_is_failure(self):
        self.upload([self.result, dict(self.result, embedding=[])])
        self.assert_no_partial_upload()

    def test_later_chunk_failure_rolls_back_parent_and_file(self):
        create = KnowledgeChunk.objects.create
        calls = []

        def fail_second(**kwargs):
            calls.append(kwargs)
            if len(calls) == 2:
                raise IntegrityError('Chunk insert failed')
            return create(**kwargs)

        with patch('ai_assistant.bots.views.KnowledgeChunk.objects.create', side_effect=fail_second):
            self.upload()
        self.assertEqual(len(calls), 2)
        self.assert_no_partial_upload()
        self.assertEqual(BotUsageLog.objects.count(), 2)

    def test_parent_insert_failure_cleans_saved_file(self):
        with patch.object(KnowledgeBase, 'save_base', side_effect=IntegrityError('Parent insert failed')):
            self.upload()
        self.assert_no_partial_upload()

    def test_storage_failure_leaves_no_knowledge(self):
        storage = KnowledgeBase._meta.get_field('file').storage
        with patch.object(storage, 'save', side_effect=OSError('Storage unavailable')):
            self.upload()
        self.assert_no_partial_upload()
