import io
import os
import re
import zipfile
from pathlib import Path

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables

from ai_assistant.static.discord_bridge.backend_url import normalize_backend_url
from .discord_auth import issue_discord_integration
from .models import Bot


@login_required
@csrf_protect
@sensitive_post_parameters("discord_token")
@sensitive_variables()
@transaction.atomic
def download_discord_bridge(request, bot_id):
    if request.method != "POST":
        return HttpResponseBadRequest("POST required.")
    profile = getattr(request.user, "profile", None)
    if profile is None or not profile.is_pro:
        return HttpResponseForbidden("Discord integration requires the Pro plan.")
    bot = get_object_or_404(Bot, id=bot_id, owner=request.user)
    discord_token = request.POST.get("discord_token", "").strip()
    # Prevent dotenv injection; Discord bot tokens use this alphabet.
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", discord_token):
        return HttpResponseBadRequest("Invalid or missing Discord token.")
    try:
        backend = normalize_backend_url(os.getenv(
            "DEFAULT_DOMAIN", "ai-assistants-8c06fcfeab86.herokuapp.com",
        ))
    except ValueError:
        return HttpResponseBadRequest("Discord backend URL is not configured correctly.")
    integration, secret = issue_discord_integration(request.user, bot)
    env_text = (f"DISCORD_TOKEN={discord_token}\n"
                f"DJANGO_API_TOKEN={secret}\n"
                f"DJANGO_BOT_ID={bot.id}\n"
                f"DJANGO_BACKEND={backend}\n")
    bridge_folder = Path(__file__).resolve().parent.parent / "static" / "discord_bridge"
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipf:
        for filename in ("bridge.py", "backend_url.py", "requirements.txt", "README.txt", "Setup_Guide.pdf", "Commands_Guide.pdf"):
            zipf.write(bridge_folder / filename, arcname=f"discord_bridge/{filename}")
        zipf.writestr("discord_bridge/.env", env_text)
    archive.seek(0)
    response = FileResponse(archive, as_attachment=True, filename="discord_bridge.zip")
    response["Cache-Control"] = "no-store, private"
    return response
