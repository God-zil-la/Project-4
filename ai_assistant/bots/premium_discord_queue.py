"""Database-backed queue; requires PREMIUM_DISCORD_QUEUE_KEY Fernet key in Heroku."""
import os

from cryptography.fernet import Fernet, InvalidToken
from django.db import IntegrityError, transaction
from django.utils import timezone
from datetime import timedelta

from .premium_discord_models import PremiumDiscordJob


class PremiumDiscordQueueError(ValueError):
    pass


def _cipher():
    key = os.environ.get("PREMIUM_DISCORD_QUEUE_KEY", "")
    if not key:
        raise PremiumDiscordQueueError("Premium Discord queue encryption is not configured.")
    try:
        return Fernet(key.encode("ascii"))
    except (ValueError, TypeError) as exc:
        raise PremiumDiscordQueueError("Invalid Premium Discord queue encryption key.") from exc


def enqueue_interaction(*, interaction_id, guild_id, application_id, token, prompt):
    encrypted_token = _cipher().encrypt(token.encode("utf-8")).decode("ascii")
    try:
        with transaction.atomic():
            PremiumDiscordJob.objects.create(
                interaction_id=interaction_id, guild_id=guild_id,
                application_id=application_id, encrypted_token=encrypted_token,
                prompt=prompt,
            )
        return True
    except IntegrityError:
        return False


def expire_stale_interactions(*, max_age_minutes=14):
    """Discord followup tokens expire after 15 minutes; never retry old AI jobs."""
    cutoff = timezone.now() - timedelta(minutes=max_age_minutes)
    return PremiumDiscordJob.objects.filter(
        status__in=["pending", "processing"], created_at__lt=cutoff,
    ).update(status="expired", encrypted_token="", prompt="", completed_at=timezone.now())


def claim_interaction():
    with transaction.atomic():
        job = PremiumDiscordJob.objects.select_for_update(skip_locked=True).filter(
            status="pending",
            created_at__gte=timezone.now() - timedelta(minutes=14),
        ).order_by("created_at").first()
        if job is None:
            return None
        job.status = "processing"
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at"])
        return job


def decrypt_token(job):
    try:
        return _cipher().decrypt(job.encrypted_token.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError) as exc:
        raise PremiumDiscordQueueError("Cannot decrypt Discord interaction token.") from exc


def finish_interaction(job, status):
    if status not in {"done", "failed"}:
        raise ValueError("Invalid job status")
    PremiumDiscordJob.objects.filter(pk=job.pk, status="processing").update(
        status=status, completed_at=timezone.now(),
        encrypted_token="", prompt="",
    )
