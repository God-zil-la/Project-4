"""Read-only campaign monitoring; USD 500 never gates entitlement or requests."""
from decimal import Decimal
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Sum
from ai_assistant.accounts.models import UserProfile


class Command(BaseCommand):
    help = 'Report K1 usage and conservative cost exposure against the USD 500 monitoring budget.'

    def handle(self, *args, **options):
        profiles = UserProfile.objects.filter(campaign_started_at__isnull=False)
        totals = profiles.aggregate(used=Sum('campaign_tokens'), reserved=Sum('campaign_reserved_tokens'))
        tokens = (totals['used'] or 0) + (totals['reserved'] or 0)
        rate = max(Decimal(str(value)) for model in ('gpt-4o-mini', 'text-embedding-3-small')
                   for value in settings.AI_MODEL_PRICING[model].values())
        exposure = Decimal(tokens) * rate / Decimal(1_000_000)
        self.stdout.write(f"Redemptions: {profiles.count()}; charged tokens: {totals['used'] or 0}; outstanding reservations: {totals['reserved'] or 0}")
        self.stdout.write(f'Conservative cost exposure: USD {exposure:.4f}; monitoring budget: USD 500.00')
        if exposure >= 500:
            self.stdout.write('REVIEW: monitoring budget reached. No automatic action taken.')
        self.stdout.write('Estimate uses the highest configured per-token price, including uncertain usage. Reconcile with provider invoices; deleted accounts are excluded.')
