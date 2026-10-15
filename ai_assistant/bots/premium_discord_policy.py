"""Premium-only Discord policy; isolated from existing Pro U5 credentials.

No Discord events or client-provided guild IDs are trusted by this module.
Server ownership proof and persistence are separate required integration steps.
"""
from dataclasses import dataclass

MAX_PREMIUM_DISCORD_GUILDS = 3


class PremiumDiscordPolicyError(ValueError):
    """A Premium Discord entitlement or guild-capacity check failed."""


@dataclass(frozen=True)
class PremiumDiscordDecision:
    eligible: bool
    active_guilds: int
    available_slots: int


def is_premium_discord_eligible(profile):
    """Require the *effective* Premium plan, not a stale stored plan.

    Pro intentionally uses the existing U5 Discord integration, not this feature.
    """
    return bool(
        profile is not None
        and getattr(profile, "effective_plan", None) == "premium"
        and getattr(getattr(profile, "user", None), "is_active", False)
    )


def check_premium_discord_capacity(profile, active_guild_ids, new_guild_id):
    """Validate capacity before installation; DB layer must lock/recheck atomically.

    An existing guild may be reauthorized without consuming another slot.
    """
    if not is_premium_discord_eligible(profile):
        raise PremiumDiscordPolicyError("An active Premium subscription is required.")
    if isinstance(new_guild_id, bool) or not str(new_guild_id).isdigit() or int(new_guild_id) <= 0:
        raise PremiumDiscordPolicyError("Invalid Discord guild ID.")
    guild_id = str(int(new_guild_id))
    guilds = {str(int(item)) for item in active_guild_ids}
    if guild_id not in guilds and len(guilds) >= MAX_PREMIUM_DISCORD_GUILDS:
        raise PremiumDiscordPolicyError("Maximum of three active Discord servers reached.")
    return PremiumDiscordDecision(
        eligible=True,
        active_guilds=len(guilds),
        available_slots=max(0, MAX_PREMIUM_DISCORD_GUILDS - len(guilds) - (guild_id not in guilds)),
    )
