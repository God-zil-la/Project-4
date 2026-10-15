"""Atomic account-wide Premium Discord guild registration.

Call connect_guild only AFTER a verified Discord OAuth guild authorization.
Never accept an unverified client-supplied guild ID as proof of ownership.
"""
from django.db import transaction
from django.utils import timezone

from ai_assistant.accounts.models import UserProfile
from .premium_discord_models import PremiumDiscordGuild
from .premium_discord_policy import (
    PremiumDiscordPolicyError,
    check_premium_discord_capacity,
    is_premium_discord_eligible,
)


@transaction.atomic
def connect_verified_guild(*, owner, guild_id, guild_name="", authorization_verified=False):
    if authorization_verified is not True:
        raise PremiumDiscordPolicyError("Verified Discord authorization is required.")
    # Lock the owner row: simultaneous installations cannot both take the final slot.
    profile = UserProfile.objects.select_for_update().select_related("user").get(user=owner)
    if not is_premium_discord_eligible(profile):
        raise PremiumDiscordPolicyError("An active Premium subscription is required.")
    guild_id = str(guild_id)
    active_ids = list(PremiumDiscordGuild.objects.filter(
        owner=owner, disconnected_at__isnull=True,
    ).values_list("guild_id", flat=True))
    check_premium_discord_capacity(profile, active_ids, guild_id)
    # A guild may not be hijacked from another account, even if disconnected.
    guild = PremiumDiscordGuild.objects.select_for_update().filter(guild_id=guild_id).first()
    if guild is not None and guild.owner_id != owner.pk:
        raise PremiumDiscordPolicyError("This Discord server is linked to another account.")
    if guild is None:
        guild = PremiumDiscordGuild(owner=owner, guild_id=guild_id)
    guild.guild_name = str(guild_name)[:100]
    guild.disconnected_at = None
    guild.save()
    return guild


@transaction.atomic
def disconnect_guild(*, owner, guild_id):
    # Lock the same owner row as connect_verified_guild for consistent ordering.
    UserProfile.objects.select_for_update().get(user=owner)
    guild = PremiumDiscordGuild.objects.select_for_update().filter(
        owner=owner, guild_id=str(guild_id), disconnected_at__isnull=True,
    ).first()
    if guild is None:
        return False
    guild.disconnected_at = timezone.now()
    guild.save(update_fields=["disconnected_at"])
    return True


def resolve_active_premium_guild(guild_id):
    """Fail closed on downgrade, deactivation or removed guild."""
    guild = PremiumDiscordGuild.objects.select_related("owner", "owner__profile").filter(
        guild_id=str(guild_id), disconnected_at__isnull=True,
    ).first()
    if guild is None or not is_premium_discord_eligible(getattr(guild.owner, "profile", None)):
        return None
    return guild
