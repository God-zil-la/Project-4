from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CustomizationMigrationTests(TransactionTestCase):
    def test_existing_assistant_and_knowledge_survive_with_neutral_defaults(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        old = [('bots', '0017_knowledgebase_source_size_bytes')]
        try:
            executor.migrate(old)
            apps = executor.loader.project_state(old).apps
            user = apps.get_model('auth', 'User').objects.create(username='migration-owner')
            bot = apps.get_model('bots', 'Bot').objects.create(
                owner_id=user.pk, name='Existing assistant', category='travel',
                description='Existing description', personality='Existing instructions',
            )
            knowledge = apps.get_model('bots', 'KnowledgeBase').objects.create(
                bot_id=bot.pk, file='existing.txt', source_size_bytes=42,
            )
            executor = MigrationExecutor(connection)
            executor.migrate(latest)
            apps = executor.loader.project_state(latest).apps
            migrated = apps.get_model('bots', 'Bot').objects.get(pk=bot.pk)
            self.assertEqual((migrated.name, migrated.description, migrated.personality, migrated.category),
                             ('Existing assistant', 'Existing description', 'Existing instructions', 'travel'))
            self.assertEqual((migrated.response_tone, migrated.response_length, migrated.avatar_icon), ('default',) * 3)
            self.assertEqual(apps.get_model('bots', 'KnowledgeBase').objects.get(pk=knowledge.pk).source_size_bytes, 42)
        finally:
            MigrationExecutor(connection).migrate(latest)
