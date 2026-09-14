"""Account erasure and retryable storage cleanup. Never cancels payments silently."""
import logging

import stripe
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import transaction

from ai_assistant.bots.models import KnowledgeBase
from ai_assistant.payments.models import (
    BillingEmail, CheckoutAttempt, SubscriptionChange, SubscriptionRecovery,
)
from .models import DeletionFollowUp, FileDeletionJob, UserProfile

logger = logging.getLogger(__name__)


class DeletionBlocked(ValueError):
    pass


def check_billing(profile):
    """Require confirmed ended billing; uncertain provider state is not consent."""
    message = (
        "Billing needs to be resolved before automatic account deletion. "
        "Manage your subscription in Billing or email support@myaiassistantapp.se "
        "to request account deletion and help ending billing. A cancellation "
        "scheduled for the end of the billing period is not an ended subscription."
    )
    if SubscriptionRecovery.objects.filter(profile=profile, completed=False).exists():
        raise DeletionBlocked(message)
    if SubscriptionChange.objects.filter(profile=profile).exclude(
        status__in=['removed', 'complete']
    ).exists():
        raise DeletionBlocked(message)
    attempt = CheckoutAttempt.objects.filter(profile=profile).first()
    if not profile.stripe_customer_id:
        if (profile.stripe_subscription_id or profile.is_subscribed
                or profile.plan != UserProfile.PLAN_FREE or attempt):
            raise DeletionBlocked(message)
        return
    try:
        if UserProfile.objects.filter(stripe_customer_id=profile.stripe_customer_id).exclude(pk=profile.pk).exists():
            raise DeletionBlocked(message)
        options = {'customer': profile.stripe_customer_id, 'limit': 100,
                   'api_key': settings.STRIPE_SECRET_KEY}
        subscriptions = list(stripe.Subscription.list(status='all', **options).auto_paging_iter())
        for sub in subscriptions:
            if (sub.get('customer') != profile.stripe_customer_id
                    or sub.get('livemode') is not settings.STRIPE_SECRET_KEY.startswith(('sk_live_', 'rk_live_'))
                    or sub.get('status') not in {'canceled', 'incomplete_expired'}):
                raise DeletionBlocked(message)
        if profile.stripe_subscription_id and not any(
            sub.get('id') == profile.stripe_subscription_id for sub in subscriptions
        ):
            raise DeletionBlocked(message)
        if any(s.get('status') not in {'completed', 'canceled', 'released'}
               for s in stripe.SubscriptionSchedule.list(**options).auto_paging_iter()):
            raise DeletionBlocked(message)
        sessions = list(stripe.checkout.Session.list(**options).auto_paging_iter())
        if any(s.get('status') not in {'complete', 'expired'} for s in sessions):
            raise DeletionBlocked(message)
        if attempt and (not attempt.session_id or not any(
            s.get('id') == attempt.session_id for s in sessions
        )):
            raise DeletionBlocked(message)
    except DeletionBlocked:
        raise
    except Exception:
        # Never expose provider responses, credentials or customer information.
        raise DeletionBlocked(
            "We could not verify billing. Your account has not been deleted. "
            "Please try again or request deletion at support@myaiassistantapp.se."
        ) from None


def cleanup_file(job_id):
    """Idempotent, after-commit cleanup; failed jobs remain for the retry command."""
    try:
        with transaction.atomic():
            job = FileDeletionJob.objects.select_for_update().filter(pk=job_id).first()
            if job is None:
                return True
            # Never erase a file still referenced by another Knowledge Base row.
            if not KnowledgeBase.objects.filter(file=job.name).exists():
                storage = KnowledgeBase._meta.get_field('file').storage
                storage.delete(job.name)
            job.delete()
        return True
    except Exception:
        logger.error('File deletion job %s needs retry', job_id)
        return False


def remove_rate_limit(user_id):
    try:
        cache.delete(f'ai-rate-limit:{user_id}')
    except Exception:
        # This counter already has a 60-second TTL in chat_service.py.
        logger.warning('Account rate-limit cleanup unavailable')


@transaction.atomic
def delete_account(user_id, *, password=None, expected_email=None):
    """Use after password verification or a support-verified ownership request."""
    user = get_user_model().objects.select_for_update().get(pk=user_id)
    if expected_email is not None and user.email.casefold() != expected_email.casefold():
        raise DeletionBlocked('Account email changed; verify ownership again before deletion.')
    if password is not None and not user.check_password(password):
        raise DeletionBlocked('Your password was not accepted. Your account has not been deleted.')
    # pre_delete enforces the same billing and cleanup rules for ORM/admin deletion.
    user.delete()
    return user._deletion_followup_id


def prepare_account_deletion(user):
    """Called inside Django's deletion transaction, including admin/bulk cascades."""
    user_id = user.pk
    profile = UserProfile.objects.select_for_update().filter(user=user).first()
    if profile is not None:
        check_billing(profile)
    follow_up = DeletionFollowUp.objects.create(
        email=user.email,
        stripe_customer_id=(profile.stripe_customer_id or '') if profile else '',
    )
    # uploaded_by is SET_NULL, so the default User cascade alone misses these.
    # Owned-bot files are already included in Django's collected CASCADE.
    KnowledgeBase.objects.filter(uploaded_by=user).exclude(bot__owner=user).delete()
    # Legacy outbox has no FK. Remove both delivered copies and unsent messages.
    if user.email:
        BillingEmail.objects.filter(recipient__iexact=user.email).delete()
    transaction.on_commit(lambda: remove_rate_limit(user_id))
    user._deletion_followup_id = follow_up.pk
