"""Command safety tests; no external connections."""

from io import StringIO
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class CleanupCommandTests(SimpleTestCase):
    def test_default_does_not_run(self):
        out = StringIO()

        with patch(
            "ai_assistant.tts.management.commands."
            "tts_cleanup_once.execute_cleanup"
        ) as execute:
            call_command("tts_cleanup_once", stdout=out)
            execute.assert_not_called()

        self.assertIn("DRY RUN", out.getvalue())

    def test_explicit_execute_without_enablement_fails(self):
        with override_settings(U62_CLEANUP_ENABLED=False):
            with self.assertRaises(CommandError):
                call_command("tts_cleanup_once", execute=True)

    def test_truthy_string_enablement_fails(self):
        with override_settings(U62_CLEANUP_ENABLED="true"):
            with self.assertRaises(CommandError):
                call_command("tts_cleanup_once", execute=True)

    def test_missing_factory_fails(self):
        with override_settings(
            U62_CLEANUP_ENABLED=True,
            U62_CLEANUP_FACTORY=None,
        ):
            with self.assertRaises(CommandError):
                call_command("tts_cleanup_once", execute=True)

    def test_invalid_batch_limits_fail(self):
        for limit in (0, -1, 101):
            with self.subTest(limit=limit):
                with self.assertRaises(CommandError):
                    call_command("tts_cleanup_once", limit=limit)

    def test_factory_failure_is_contained(self):
        with override_settings(
            U62_CLEANUP_ENABLED=True,
            U62_CLEANUP_FACTORY="test.factory",
        ):
            with patch(
                "ai_assistant.tts.management.commands."
                "tts_cleanup_once.import_string",
                side_effect=RuntimeError("unavailable"),
            ):
                with self.assertRaises(CommandError):
                    call_command("tts_cleanup_once", execute=True)

    def test_explicit_run_uses_injected_dependencies(self):
        repository = Mock()
        store = Mock()
        out = StringIO()

        with override_settings(
            U62_CLEANUP_ENABLED=True,
            U62_CLEANUP_FACTORY="test.factory",
        ):
            with patch(
                "ai_assistant.tts.management.commands."
                "tts_cleanup_once.import_string",
                return_value=lambda: (repository, store),
            ):
                with patch(
                    "ai_assistant.tts.management.commands."
                    "tts_cleanup_once.execute_cleanup",
                    return_value={"deleted": 3, "retried": 1},
                ) as execute:
                    call_command(
                        "tts_cleanup_once",
                        execute=True,
                        limit=7,
                        stdout=out,
                    )

        execute.assert_called_once_with(
            repository=repository,
            audio_store=store,
            enabled=True,
            limit=7,
        )
        self.assertIn("deleted=3", out.getvalue())

    def test_cleanup_failure_is_contained(self):
        with override_settings(
            U62_CLEANUP_ENABLED=True,
            U62_CLEANUP_FACTORY="test.factory",
        ):
            with patch(
                "ai_assistant.tts.management.commands."
                "tts_cleanup_once.import_string",
                return_value=lambda: (Mock(), Mock()),
            ):
                with patch(
                    "ai_assistant.tts.management.commands."
                    "tts_cleanup_once.execute_cleanup",
                    side_effect=RuntimeError("cleanup failed"),
                ):
                    with self.assertRaises(CommandError):
                        call_command("tts_cleanup_once", execute=True)
