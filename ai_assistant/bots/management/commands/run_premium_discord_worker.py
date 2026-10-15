"""Dedicated worker for Premium Discord; no U5 Pro worker changes."""
from django.core.management.base import BaseCommand
from ai_assistant.bots.premium_discord_worker import run_worker


class Command(BaseCommand):
    help = "Process Premium Discord interaction jobs (requires a separate worker process)."

    def handle(self, *args, **options):
        self.stdout.write("Premium Discord worker started.")
        run_worker()
