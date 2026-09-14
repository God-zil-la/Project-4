from django.core.management.base import BaseCommand, CommandError
from ai_assistant.accounts.models import DeletionFollowUp


class Command(BaseCommand):
    help = 'Erase minimal follow-up contact data after provider/support erasure is resolved.'

    def add_arguments(self, parser):
        parser.add_argument('--id', required=True, type=int)
        parser.add_argument('--provider-review-complete', action='store_true')

    def handle(self, *args, **options):
        if not options['provider_review_complete']:
            raise CommandError('Complete provider erasure, communicate exceptions, and notify the user first.')
        deleted, _ = DeletionFollowUp.objects.filter(pk=options['id']).delete()
        if not deleted:
            raise CommandError('No matching pending follow-up.')
        self.stdout.write('Follow-up contact data erased.')
