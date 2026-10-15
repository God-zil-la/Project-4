"""Premium-only OAuth management endpoints, isolated from Pro U5."""
import secrets

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET, require_POST

from .premium_discord_discord_api import (
    DiscordOAuthError, authorization_url, authorized_manageable_guilds, exchange_code, verify_bot_membership,
)
from .premium_discord_guild_service import connect_verified_guild, disconnect_guild
from .premium_discord_models import PremiumDiscordGuild
from .premium_discord_oauth import create_oauth_state, validate_oauth_state
from .premium_discord_policy import PremiumDiscordPolicyError, is_premium_discord_eligible


def _premium(user):
    return is_premium_discord_eligible(getattr(user, "profile", None))


@login_required
@require_GET
def premium_discord_status(request):
    if not _premium(request.user):
        return JsonResponse({"error": "Premium required"}, status=403)
    guilds = PremiumDiscordGuild.objects.filter(
        owner=request.user, disconnected_at__isnull=True,
    ).values("guild_id", "guild_name")
    return JsonResponse({"guilds": list(guilds), "limit": 3})


@login_required
@require_GET
def premium_discord_connect(request):
    if not _premium(request.user):
        return JsonResponse({"error": "Premium required"}, status=403)
    state = create_oauth_state(request.user.pk)
    # Session binding makes the signed state single-use and blocks login CSRF.
    request.session["premium_discord_oauth_state"] = state
    try:
        url = authorization_url(state)
    except DiscordOAuthError:
        return JsonResponse({"error": "Discord OAuth unavailable"}, status=503)
    return redirect(url)


@login_required
@require_GET
def premium_discord_callback(request):
    state = request.GET.get("state", "")
    expected = request.session.pop("premium_discord_oauth_state", None)
    if not expected or not secrets.compare_digest(state, expected):
        return HttpResponseBadRequest("Invalid or already-used Discord authorization.")
    try:
        validate_oauth_state(state, request.user.pk)
        if not _premium(request.user):
            return JsonResponse({"error": "Premium required"}, status=403)
        code = request.GET.get("code", "")
        token = exchange_code(code)
        guilds = authorized_manageable_guilds(token)
        # Guild selection happens after verified OAuth, using a short-lived session
        # allowlist. Never accept arbitrary guild IDs from the client.
        request.session["premium_discord_verified_guilds"] = guilds
        request.session["premium_discord_verified_at"] = __import__("time").time()
        return JsonResponse({"authorized_guilds": [
            {"guild_id": guild_id, "guild_name": name}
            for guild_id, name in guilds.items()
        ], "next": "POST /bots/api/premium-discord/guilds/connect/"})
    except (DiscordOAuthError, ValidationError):
        return HttpResponseBadRequest("Discord authorization failed.")


@login_required
@require_POST
def premium_discord_add_guild(request):
    if not _premium(request.user):
        return JsonResponse({"error": "Premium required"}, status=403)
    guild_id = request.POST.get("guild_id", "")
    guilds = request.session.get("premium_discord_verified_guilds", {})
    verified_at = request.session.get("premium_discord_verified_at", 0)
    import time
    if not isinstance(verified_at, (int, float)) or time.time() - verified_at > 600:
        request.session.pop("premium_discord_verified_guilds", None)
        request.session.pop("premium_discord_verified_at", None)
        return JsonResponse({"error": "Discord verification expired"}, status=403)
    if not isinstance(guilds, dict) or guild_id not in guilds:
        return JsonResponse({"error": "Discord server permission not verified"}, status=403)
    # Consume authorization for this server before creating the record.
    guild_name = guilds[guild_id]
    try:
        verify_bot_membership(guild_id)
    except DiscordOAuthError:
        return JsonResponse({"error": "Install the Premium Discord bot on this server first"}, status=403)
    guilds.pop(guild_id)
    request.session["premium_discord_verified_guilds"] = guilds
    request.session.modified = True
    try:
        guild = connect_verified_guild(
            owner=request.user, guild_id=guild_id, guild_name=guild_name,
            authorization_verified=True,
        )
    except PremiumDiscordPolicyError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    return JsonResponse({"guild_id": guild.guild_id, "guild_name": guild.guild_name})


@login_required
@require_POST
def premium_discord_remove_guild(request):
    if not _premium(request.user):
        return JsonResponse({"error": "Premium required"}, status=403)
    guild_id = request.POST.get("guild_id", "")
    if not guild_id.isdecimal():
        return JsonResponse({"error": "Invalid guild ID"}, status=400)
    return JsonResponse({"disconnected": disconnect_guild(owner=request.user, guild_id=guild_id)})
