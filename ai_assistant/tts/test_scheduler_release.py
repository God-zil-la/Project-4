"""No-network tests for scheduler invocation of the existing one-shot command.

These tests NEVER start a scheduler or access a real object store.
"""
from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


COMMAND = "ai_assistant.tts.management.commands.tts_cleanup_once"


class SchedulerReleaseContractTests(SimpleTestCase):
    def test_scheduled_command_without_execute_is_dry_run(self):
        output = StringIO()
        with override_settings(U62_CLEANUP_ENABLED=True):
            with patch(COMMAND + ".import_string") as import_factory:
                call_command("tts_cleanup_once", stdout=output, limit=50)
        import_factory.assert_not_called()
        self.assertIn("DRY RUN", output.getvalue())

    def test_execute_is_rejected_with_cleanup_disabled(self):
        with override_settings(U62_CLEANUP_ENABLED=False):
            with patch(COMMAND + ".import_string") as import_factory:
                with self.assertRaises(CommandError):
                    call_command("tts_cleanup_once", execute=True, limit=50)
        import_factory.assert_not_called()

    def test_execute_does_not_accept_truthy_string_enablement(self):
        with override_settings(U62_CLEANUP_ENABLED="true"):
            with self.assertRaises(CommandError):
                call_command("tts_cleanup_once", execute=True, limit=50)

    def test_explicit_scheduled_run_uses_only_injected_fakes(self):
        repository, store = Mock(), Mock()
        output = StringIO()
        with override_settings(
            U62_CLEANUP_ENABLED=True,
            U62_CLEANUP_FACTORY="test.injected_factory",
        ):
            with patch(COMMAND + ".import_string", return_value=lambda: (repository, store)):
                with patch(
                    COMMAND + ".execute_cleanup",
                    return_value={"deleted": 2, "retried": 1},
                ) as execute:
                    call_command(
                        "tts_cleanup_once", execute=True, limit=50, stdout=output
                    )
        execute.assert_called_once_with(
            repository=repository,
            audio_store=store,
            enabled=True,
            limit=50,
        )
        self.assertIn("deleted=2", output.getvalue())
        self.assertIn("retried=1", output.getvalue())
        store.delete_object.assert_not_called()
