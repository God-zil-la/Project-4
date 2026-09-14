from django.core.management.base import BaseCommand, CommandError
from ai_assistant.accounts.deletion import cleanup_file
from ai_assistant.accounts.models import FileDeletionJob


class Command(BaseCommand):
    help = 'Retry pending uploaded-file deletions; exits with an error if any fail.'

    def handle(self, *args, **options):
        failed = 0
        for pk in FileDeletionJob.objects.values_list('pk', flat=True).iterator():
            if not cleanup_file(pk):
                failed += 1
        if failed:
            raise CommandError(f'{failed} file deletion jobs still need retry.')
        self.stdout.write('Pending file deletions processed.')
