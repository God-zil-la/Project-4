from django.db import models

class StripeEvent(models.Model):
    """Processed event identifiers only; never persist payment payloads."""
    event_id = models.CharField(max_length=255, unique=True)
    processed_at = models.DateTimeField(auto_now_add=True)
