import uuid

from django.conf import settings
from django.db import models


class VoiceSession(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    assistant = models.ForeignKey("bots.Bot", on_delete=models.CASCADE)
    conversation = models.ForeignKey("bots.Conversation", on_delete=models.CASCADE)
    quota_reservation = models.OneToOneField(
        "LiveVoiceQuotaReservation", on_delete=models.PROTECT,
        null=True, blank=True, related_name="session",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    deadline_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)


class VoiceTurn(models.Model):
    class State(models.TextChoices):
        CREATED = "created", "Created"
        TRANSCRIBING = "transcribing", "Transcribing"
        TRANSCRIBED = "transcribed", "Transcribed"
        PROCESSING = "processing", "Processing"
        ANSWER_SAVED = "answer_saved", "Answer saved"
        SYNTHESIZING = "synthesizing", "Synthesizing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        UNCERTAIN = "uncertain", "Uncertain"

    session = models.ForeignKey(
        VoiceSession, on_delete=models.CASCADE, related_name="turns"
    )
    request_id = models.UUIDField()
    audio_sha256 = models.CharField(max_length=64)
    state = models.CharField(
        max_length=20, choices=State.choices, default=State.CREATED
    )
    output_audio_key = models.UUIDField(null=True, blank=True, editable=False)
    output_audio_sha256 = models.CharField(max_length=64, blank=True, editable=False)
    transcript = models.TextField(blank=True)
    assistant_message = models.ForeignKey(
        "bots.ChatMessage", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="voice_turns"
    )
    error_code = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session", "request_id"],
                name="u63_unique_session_request",
            )
        ]


# U6.3 Live Voice monthly quota models.
from .live_quota_models import LiveVoiceMonthlyUsage, LiveVoiceQuotaReservation
