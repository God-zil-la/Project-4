"""Exercise the index against existing data and verify safe rollback."""
from django.db import connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class UsernameMigrationTests(TransactionTestCase):
    before = [("accounts", "0010_userprofile_complimentary_plan_and_more")]
    after = [("accounts", "0011_unique_username_case_insensitive")]

    def migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        return executor.loader.project_state(target).apps

    def setUp(self):
        super().setUp()
        apps = self.migrate(self.before)
        self.user_model = apps.get_model("auth", "User")

    def tearDown(self):
        # Remove fixtures before restoring the index, even after a failed assertion.
        self.user_model.objects.all().delete()
        self.migrate(self.after)
        super().tearDown()

    def test_existing_account_is_preserved_and_index_is_reversible(self):
        user = self.user_model.objects.create(
            username="Funcy92", password="existing-password-hash", is_active=False,
        )
        self.migrate(self.after)
        user.refresh_from_db()
        self.assertEqual(user.username, "Funcy92")
        self.assertEqual(user.password, "existing-password-hash")
        self.assertFalse(user.is_active)
        with self.assertRaises(IntegrityError), transaction.atomic():
            self.user_model.objects.create(username="FUNCY92")
        self.migrate(self.before)
        self.user_model.objects.create(username="FUNCY92")
        self.assertEqual(self.user_model.objects.count(), 2)

    def test_existing_collisions_stop_migration_without_modifying_accounts(self):
        self.user_model.objects.create(username="Funcy92")
        self.user_model.objects.create(username="funcy92")
        before = list(self.user_model.objects.order_by("pk").values())
        with self.assertRaisesMessage(RuntimeError, "Case-insensitive username collisions exist"):
            self.migrate(self.after)
        self.assertEqual(list(self.user_model.objects.order_by("pk").values()), before)
