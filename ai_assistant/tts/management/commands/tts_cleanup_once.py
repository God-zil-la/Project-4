"""Explicit, disabled-by-default TTS cleanup command.

No scheduler, credentials, or storage client is created on import.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.module_loading import import_string

from ...cleanup_runner import execute_cleanup


class Command(BaseCommand):
    help = "Run one explicitly authorized TTS audio cleanup batch"

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Request an actual cleanup batch",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum number of cleanup jobs (1-100)",
        )

    def handle(self, *args, **options):
        limit = options["limit"]

        if type(limit) is not int or not 1 <= limit <= 100:
            raise CommandError("Invalid cleanup limit")

        if not options["execute"]:
            self.stdout.write(
                "DRY RUN: TTS cleanup disabled. "
                "No database or R2 operations performed."
            )
            return

        if getattr(settings, "U62_CLEANUP_ENABLED", False) is not True:
            raise CommandError(
                "TTS cleanup not enabled in Django settings"
            )

        factory_path = getattr(
            settings, "U62_CLEANUP_FACTORY", None
        )

        if not isinstance(factory_path, str) or not factory_path:
            raise CommandError(
                "Reviewed cleanup dependency factory required"
            )

        try:
            factory = import_string(factory_path)
            repository, audio_store = factory()
        except Exception as exc:
            raise CommandError(
                "Cleanup dependencies could not be initialized"
            ) from exc

        if repository is None or audio_store is None:
            raise CommandError("Invalid cleanup dependencies")

        try:
            result = execute_cleanup(
                repository=repository,
                audio_store=audio_store,
                enabled=True,
                limit=limit,
            )
        except Exception as exc:
            raise CommandError("TTS cleanup batch failed") from exc

        self.stdout.write(
            "Cleanup completed: "
            f"deleted={result['deleted']}, "
            f"retried={result['retried']}"
        )
