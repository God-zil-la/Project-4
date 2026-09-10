"""Recover committed notifications whose callback never ran."""
from django.core.management.base import BaseCommand
from ai_assistant.payments.emails import deliver
from ai_assistant.payments.models import BillingEmail


class Command(BaseCommand):
    help = "Send pending billing emails only; never retry failed or ambiguous attempts."

    def handle(self, *args, **options):
        for pk in BillingEmail.objects.filter(status="pending").values_list("pk", flat=True).iterator():
            deliver(pk)
