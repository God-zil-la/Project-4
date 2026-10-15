"""Premium Discord interaction entrypoint, independent of existing Pro U5."""
import json
import logging

import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .premium_discord_queue import enqueue_interaction, PremiumDiscordQueueError
from .premium_discord_signature import (
    DiscordInteractionVerificationError, verify_discord_interaction,
)

logger = logging.getLogger(__name__)


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
    try:
        enqueue_interaction(
            interaction_id=interaction_id, guild_id=guild_id,
            application_id=application_id, token=token, prompt=prompt.strip(),
        )
    except PremiumDiscordQueueError:
        logger.error("Premium Discord queue encryption is not configured")
        return JsonResponse({"error": "Discord queue unavailable"}, status=503)
    # Discord expects an acknowledgement within three seconds. A dedicated
    # worker processes the persisted job; web dyno restarts cannot lose it.
    return JsonResponse({"type": 5})
