from io import StringIO
from unittest.mock import patch
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from ai_assistant.bots.models import Bot, Conversation

class SecurityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='security-owner')
        self.user.profile.generate_api_key()
        self.bot = Bot.objects.create(owner=self.user, name='Private')
        self.url = '/accounts/api/public-chat/'

    def test_rotation_invalidates_old_key_without_output(self):
        old = self.user.profile.api_key
        output = StringIO()
        call_command('rotate_public_api_key', username=self.user.username, stdout=output)
        self.user.profile.refresh_from_db()
        new = self.user.profile.api_key
        self.assertNotEqual(old, new)
        self.assertNotIn(old, output.getvalue())
        self.assertNotIn(new, output.getvalue())
        self.assertEqual(self.client.post(self.url, HTTP_X_API_KEY=old).status_code, 401)
        with patch('ai_assistant.accounts.api_views.process_bot_message', return_value={'response': 'ok'}):
            self.assertEqual(self.client.post(self.url, {'bot_id': self.bot.pk, 'message': 'Hello'},
                             HTTP_X_API_KEY=new).status_code, 200)

    def test_inactive_user_rejected(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.client.post(self.url, HTTP_X_API_KEY=self.user.profile.api_key).status_code, 401)

    def test_bad_bot_id_and_foreign_bot(self):
        for bot_id in ['invalid', 999999]:
            self.assertEqual(self.client.post(self.url, {'bot_id': bot_id, 'message': 'Hello'},
                HTTP_X_API_KEY=self.user.profile.api_key).status_code, 404)

    def test_foreign_conversation_cannot_be_read_renamed_or_deleted(self):
        other = User.objects.create_user(username='other-owner')
        conversation = Conversation.objects.create(user=other, bot=self.bot)
        self.client.force_login(self.user)
        url = f'/bots/api/conversations/{conversation.public_id}/'
        for method in ['get', 'patch', 'delete']:
            response = getattr(self.client, method)(url, content_type='application/json')
            self.assertEqual(response.status_code, 404)
        self.assertTrue(Conversation.objects.filter(pk=conversation.pk).exists())
