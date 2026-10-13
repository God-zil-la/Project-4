"""Invalidate one account's public API key without printing either key."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from ai_assistant.accounts.models import UserProfile


class Command(BaseCommand):
    help = 'Rotate one public API key. The replacement is discarded; the customer must create a new key from API Access.'

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)

    def handle(self, *args, **options):
        with transaction.atomic():
            try:
                profile = UserProfile.objects.select_for_update().get(user__username=options['username'])
            except UserProfile.DoesNotExist:
                raise CommandError('Account not found.') from None
            profile.generate_api_key()
        self.stdout.write(self.style.SUCCESS('Public API key invalidated. Create a replacement from the account API Access page.'))
