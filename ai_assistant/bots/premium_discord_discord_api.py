"""Discord OAuth API for Premium guild installation.

Credentials must be supplied via Heroku environment variables. No Pro API calls.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request


class DiscordOAuthError(ValueError):
    pass


def _credentials():
    client_id = os.environ.get("PREMIUM_DISCORD_CLIENT_ID", "").strip()
    client_secret = os.environ.get("PREMIUM_DISCORD_CLIENT_SECRET", "").strip()
    redirect_uri = os.environ.get("PREMIUM_DISCORD_REDIRECT_URI", "").strip()
    if not all((client_id, client_secret, redirect_uri)):
        raise DiscordOAuthError("Premium Discord OAuth is not configured.")
    if not redirect_uri.startswith("https://"):
        raise DiscordOAuthError("Discord redirect URI must use HTTPS.")
    return client_id, client_secret, redirect_uri


def authorization_url(state):
    client_id, _, redirect_uri = _credentials()
    params = urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "identify guilds bot applications.commands",
        "permissions": "2048",
        "state": state,
        "prompt": "consent",
    })
    return "https://discord.com/oauth2/authorize?" + params


def _discord_json(url, *, token=None, form=None):
    headers = {"Accept": "application/json", "User-Agent": "AI-Assistant-Premium-Discord/1.0"}
    data = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if form is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        data = urllib.parse.urlencode(form).encode("ascii")
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = response.read(262144)
        result = json.loads(payload)
    except (urllib.error.URLError, ValueError, OSError) as exc:
        raise DiscordOAuthError("Discord authorization could not be verified.") from exc
    if not isinstance(result, (dict, list)):
        raise DiscordOAuthError("Unexpected Discord response.")
    return result


def exchange_code(code):
    if not isinstance(code, str) or not code or len(code) > 2048:
        raise DiscordOAuthError("Invalid Discord authorization code.")
    client_id, client_secret, redirect_uri = _credentials()
    result = _discord_json("https://discord.com/api/v10/oauth2/token", form={
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    })
    token = result.get("access_token") if isinstance(result, dict) else None
    if not isinstance(token, str) or not token:
        raise DiscordOAuthError("Discord did not provide an access token.")
    return token


def authorized_manageable_guilds(access_token):
    guilds = _discord_json("https://discord.com/api/v10/users/@me/guilds", token=access_token)
    if not isinstance(guilds, list):
        raise DiscordOAuthError("Invalid Discord guild list.")
    # Discord permission bit 0x20 = MANAGE_GUILD; owner is always authorized.
    result = {}
    for guild in guilds:
        if not isinstance(guild, dict):
            continue
        guild_id = guild.get("id")
        try:
            permissions = int(guild.get("permissions", "0"))
        except (TypeError, ValueError):
            continue
        if isinstance(guild_id, str) and guild_id.isdecimal() and (
            guild.get("owner") is True or permissions & 0x20
        ):
            result[guild_id] = str(guild.get("name", ""))[:100]
    return result


def verify_bot_membership(guild_id):
    """Verify the actual installation with the bot token; OAuth guild access alone is insufficient."""
    if not isinstance(guild_id, str) or not guild_id.isdecimal():
        raise DiscordOAuthError("Invalid Discord server.")
    bot_token = os.environ.get("PREMIUM_DISCORD_BOT_TOKEN", "").strip()
    if not bot_token:
        raise DiscordOAuthError("Premium Discord bot token is not configured.")
    request = urllib.request.Request(
        "https://discord.com/api/v10/guilds/" + guild_id,
        headers={"Authorization": "Bot " + bot_token, "User-Agent": "AI-Assistant-Premium-Discord/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read(262144))
    except (urllib.error.URLError, ValueError, OSError) as exc:
        raise DiscordOAuthError("Premium Discord bot is not installed on this server.") from exc
    if not isinstance(data, dict) or data.get("id") != guild_id:
        raise DiscordOAuthError("Premium Discord bot membership could not be verified.")
    return True
