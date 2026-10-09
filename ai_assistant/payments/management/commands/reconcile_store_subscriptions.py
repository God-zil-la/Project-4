"""Operational fallback for missed store notifications; schedule after deployment."""
from django.core.management.base import BaseCommand, CommandError

from ai_assistant.payments.models import StoreIdentity
from ai_assistant.payments.store_service import refresh_subscriptions


class Command(BaseCommand):
    help = 'Refresh store subscriptions from their providers; no client claims are used.'

    def add_arguments(self, parser):
        parser.add_argument('--profile-id', type=int)

    def handle(self, *args, **options):
        identities = StoreIdentity.objects.filter(profile__isnull=False).select_related('profile__user')
        if options['profile_id']:
            identities = identities.filter(profile_id=options['profile_id'])
        failures = 0
        for identity in identities.iterator():
            try:
                refresh_subscriptions(identity.profile.user)
            except Exception:
                failures += 1
                self.stderr.write(f'Profile {identity.profile_id}: reconciliation failed; retry required.')
        if failures:
            raise CommandError(f'{failures} account(s) need retry. No credentials or tokens logged.')
        self.stdout.write('Store reconciliation complete.')
