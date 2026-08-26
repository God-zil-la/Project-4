import os
import tempfile
import zipfile

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponseBadRequest
from rest_framework.authtoken.models import Token

from .models import Bot


@login_required
def download_discord_bridge(request, bot_id):

    if request.method != "POST":
        return HttpResponseBadRequest("POST required.")

    bot = Bot.objects.get(
        id=bot_id,
        owner=request.user,
    )

    token, _ = Token.objects.get_or_create(
        user=request.user
    )

    discord_token = request.POST.get(
        "discord_token",
        ""
    ).strip()

    if not discord_token:
        return HttpResponseBadRequest(
            "Discord token missing."
        )

    backend = os.getenv(
        "DEFAULT_DOMAIN",
        "ai-assistants-8c06fcfeab86.herokuapp.com"
    )

    temp_dir = tempfile.mkdtemp()

    env_text = f"""DISCORD_TOKEN={discord_token}

DJANGO_API_TOKEN={token.key}

DJANGO_BOT_ID={bot.id}

DJANGO_BACKEND=https://{backend}
"""

    with open(
        os.path.join(temp_dir, ".env"),
        "w",
        encoding="utf-8",
    ) as f:
        f.write(env_text)

    bridge_folder = os.path.join(
        "ai_assistant",
        "static",
        "discord_bridge",
    )

    zip_path = os.path.join(
        temp_dir,
        "discord_bridge.zip",
    )

    with zipfile.ZipFile(
        zip_path,
        "w",
        zipfile.ZIP_DEFLATED,
    ) as zipf:

        files = [
            "bridge.py",
            "requirements.txt",
            "Setup_Guide.pdf",
            "Commands_Guide.pdf",
        ]

        for filename in files:

            file_path = os.path.join(
                bridge_folder,
                filename,
            )

            if not os.path.exists(file_path):
                raise FileNotFoundError(file_path)

            zipf.write(
                file_path,
                arcname=f"discord_bridge/{filename}",
            )

        zipf.write(
            os.path.join(temp_dir, ".env"),
            arcname="discord_bridge/.env",
        )

    return FileResponse(
        open(zip_path, "rb"),
        as_attachment=True,
        filename="discord_bridge.zip",
    )