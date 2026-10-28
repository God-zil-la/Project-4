from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from ai_assistant.voice.models import VoiceSession
from ai_assistant.voice.service import reconcile_expired_sessions

class Command(BaseCommand):
    help = "Settle expired U6.3 sessions exactly once; no external calls."
    def handle(self, *args, **options):
        users = VoiceSession.objects.filter(active=True, deadline_at__lte=timezone.now()).values_list("user_id", flat=True).distinct()
        for user in get_user_model().objects.filter(pk__in=users):
            reconcile_expired_sessions(user=user)
