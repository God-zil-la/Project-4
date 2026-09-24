from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class WidgetMigrationTests(TransactionTestCase):
    def test_existing_assistants_and_chats_stay_private(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old = [('bots', '0018_assistant_customization')]
        try:
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            user = apps.get_model('auth', 'User').objects.create(username='widget-migration')
            bots = [apps.get_model('bots', 'Bot').objects.create(owner_id=user.pk, name=f'Existing {n}', response_tone='friendly') for n in range(3)]
            conversation = apps.get_model('bots', 'Conversation').objects.create(bot_id=bots[0].pk, user_id=user.pk, title='Private conversation')
            message = apps.get_model('bots', 'ChatMessage').objects.create(bot_id=bots[0].pk, user_id=user.pk, conversation_id=conversation.pk, sender='user', message='Existing history')
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            apps = executor.loader.project_state(latest).apps
            for bot in apps.get_model('bots', 'Bot').objects.all():
                self.assertFalse(bot.widget_enabled)
                self.assertIsNone(bot.widget_public_id)
                self.assertEqual(bot.response_tone, 'friendly')
            migrated = apps.get_model('bots', 'Conversation').objects.get(pk=conversation.pk)
            self.assertFalse(migrated.is_widget)
            self.assertEqual(migrated.title, 'Private conversation')
            self.assertEqual(apps.get_model('bots', 'ChatMessage').objects.get(pk=message.pk).message, 'Existing history')
        finally:
            MigrationExecutor(connection).migrate(latest)
