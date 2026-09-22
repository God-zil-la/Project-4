"""Validation shared by the assistant forms and token API."""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from .models import Bot

NAME_REQUIRED = "Please enter a name for your assistant."
NAME_TOO_LONG = "Use 100 characters or fewer for the assistant name."
PERSONALITY_REQUIRED = "Please enter personality and instructions for your assistant."
DUPLICATE_NAME = "You already have a bot with this name. Please choose a different name."


def validate_unique_name(name, owner, instance=None):
    duplicates = Bot.objects.filter(owner=owner, name=name)
    if instance is not None and instance.pk:
        duplicates = duplicates.exclude(pk=instance.pk)
    if duplicates.exists():
        raise ValidationError(DUPLICATE_NAME)
    return name


def save_assistant(bot):
    """Keep a simultaneous duplicate write a field error, not a server error."""
    try:
        with transaction.atomic():
            bot.save()
    except IntegrityError:
        validate_unique_name(bot.name, bot.owner, bot)
        raise
    return bot
