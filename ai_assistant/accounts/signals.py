from django.db.models.signals import post_save, post_delete, pre_delete
from django.db import transaction
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import UserProfile
from .utils import generate_unique_api_key
from ai_assistant.bots.models import KnowledgeBase
from .models import FileDeletionJob


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a UserProfile when a new User is created."""
    if created:
        UserProfile.objects.create(
            user=instance,
            api_key=generate_unique_api_key()
        )


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the UserProfile when the User is saved."""
    if hasattr(instance, 'profile'):
        instance.profile.save()


@receiver(post_delete, sender=KnowledgeBase)
def queue_knowledge_file_deletion(sender, instance, using, **kwargs):
    """Covers individual, assistant and account cascades without deleting before commit."""
    if instance.file and instance.file.name:
        from .deletion import cleanup_file
        job, _ = FileDeletionJob.objects.using(using).get_or_create(name=instance.file.name)
        transaction.on_commit(lambda: cleanup_file(job.pk), using=using)


@receiver(pre_delete, sender=User)
def prepare_user_deletion(sender, instance, **kwargs):
    from .deletion import prepare_account_deletion
    prepare_account_deletion(instance)
