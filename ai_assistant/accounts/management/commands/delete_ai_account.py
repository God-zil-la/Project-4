from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from ai_assistant.accounts.deletion import DeletionBlocked, delete_account


class Command(BaseCommand):
    help = 'Delete an account only after support has verified the requester owns it.'

    def add_arguments(self, parser):
        parser.add_argument('--user-id', required=True, type=int)
        parser.add_argument('--confirm-email', required=True)
        parser.add_argument('--ownership-verified', action='store_true')

    def handle(self, *args, **options):
        user = get_user_model().objects.filter(pk=options['user_id']).first()
        if (not options['ownership_verified'] or user is None
                or not user.email or user.email.casefold() != options['confirm_email'].casefold()):
            raise CommandError('A verified owner request, user ID and matching account email are required.')
        try:
            follow_up = delete_account(user.pk, expected_email=options['confirm_email'])
        except DeletionBlocked as exc:
            raise CommandError(str(exc)) from None
        self.stdout.write(f'Application account deleted. Complete provider follow-up {follow_up}.')
