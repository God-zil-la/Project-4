"""Premium Discord interaction entrypoint, independent of existing Pro U5."""
import json
import logging
from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .premium_discord_chat import answer_premium_discord
from .premium_discord_signature import (
    DiscordInteractionVerificationError, verify_discord_interaction,
)

logger = logging.getLogger(__name__)
_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="premium-discord")


def _followup(token, application_id, content):
    # Discord interaction tokens are short-lived; never log or persist them.
    if not token or not application_id:
        return
    try:
        requests.post(
            "https://discord.com/api/v10/webhooks/{}/{}".format(application_id, token),
            json={"content": content[:1900], "allowed_mentions": {"parse": []}},
            timeout=10,
        ).raise_for_status()
    except requests.RequestException:
        logger.warning("Premium Discord followup delivery failed")


def _respond(guild_id, prompt, token, application_id):
    try:
        content = answer_premium_discord(guild_id=guild_id, message=prompt)
    except Exception:
        logger.exception("Premium Discord interaction failed")
        content = "AI Assistant is unavailable or the account's usage limit was reached."
    _followup(token, application_id, content)


@csrf_exempt
@require_POST
def premium_discord_interaction(request):
    if len(request.body) > 16384:
        return JsonResponse({"error": "Payload too large"}, status=413)
    try:
        verify_discord_interaction(
            body=request.body,
            signature=request.headers.get("X-Signature-Ed25519", ""),
            timestamp=request.headers.get("X-Signature-Timestamp", ""),
        )
    except DiscordInteractionVerificationError:
        return JsonResponse({"error": "Invalid signature"}, status=401)
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({"error": "Invalid payload"}, status=400)
    if payload.get("type") == 1:
        return JsonResponse({"type": 1})
    if payload.get("type") != 2:
        return JsonResponse({"type": 4, "data": {"content": "Unsupported interaction.", "flags": 64}})
    data = payload.get("data") or {}
    if not isinstance(data, dict) or data.get("name") != "ask":
        return JsonResponse({"type": 4, "data": {"content": "Unsupported command.", "flags": 64}})
    guild_id = payload.get("guild_id")
    token = payload.get("token")
    application_id = payload.get("application_id")
    interaction_id = payload.get("id")
    options = data.get("options") or []
    prompt = next((x.get("value") for x in options if isinstance(x, dict) and x.get("name") == "question"), None) if isinstance(options, list) else None
    if not (isinstance(guild_id, str) and guild_id.isdecimal()
            and isinstance(prompt, str) and 0 < len(prompt.strip()) <= 2000
            and isinstance(token, str) and isinstance(application_id, str)
            and isinstance(interaction_id, str)):
        return JsonResponse({"type": 4, "data": {"content": "Invalid command or server.", "flags": 64}})
    # Fail closed on duplicate Discord retries, before consuming AI quota.
    if not cache.add("premium-discord-interaction:" + interaction_id, 1, timeout=900):
        return JsonResponse({"type": 5})
    _pool.submit(_respond, guild_id, prompt, token, application_id)
    return JsonResponse({"type": 5})
