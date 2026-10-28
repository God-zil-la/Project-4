import uuid
from django.conf import settings
from django.db import models
from django.db.models import Q


class TTSAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lock_version = models.PositiveBigIntegerField(default=0)


class TTSRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(TTSAccount, on_delete=models.CASCADE)
    assistant_id = models.PositiveBigIntegerField()
    request_id = models.UUIDField()
    fingerprint = models.CharField(max_length=64)
    state = models.CharField(max_length=16, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account', 'request_id'], name='tts_unique_request'),
            models.CheckConstraint(condition=Q(assistant_id__gt=0), name='tts_positive_assistant'),
            models.CheckConstraint(condition=Q(state__in=['pending', 'dispatched', 'succeeded',
                'not_processed', 'uncertain']), name='tts_valid_state'),
        ]
