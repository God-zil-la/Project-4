"""Native Discord integration management for Android and iOS."""
import base64
import io
import os
import re
import zipfile
from pathlib import Path
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from ai_assistant.static.discord_bridge.backend_url import normalize_backend_url
from .discord_auth import issue_discord_integration
from .models import Bot, DiscordIntegration

@method_decorator(never_cache, name="dispatch")
class NativeDiscordView(APIView):
    permission_classes = [IsAuthenticated]

    def _bot(self, request, bot_id):
        return get_object_or_404(Bot, pk=bot_id, owner=request.user)

    def get(self, request, bot_id):
        bot = self._bot(request, bot_id)
        integrations = DiscordIntegration.objects.filter(owner=request.user, bot=bot, revoked_at__isnull=True).order_by('-created_at')
        return Response({"is_pro": request.user.profile.is_pro, "integrations": [
            {"id": row.pk, "created_at": row.created_at.isoformat()} for row in integrations
        ]})

    @sensitive_variables()
    def post(self, request, bot_id):
        bot = self._bot(request, bot_id)
        if not request.user.profile.is_pro:
            return Response({"detail": "Pro required."}, status=403)
        token = request.data.get('discord_token')
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+', token):
            return Response({"detail": "Invalid Discord bot token."}, status=400)
        try:
            backend = normalize_backend_url(os.getenv('DEFAULT_DOMAIN', 'ai-assistants-8c06fcfeab86.herokuapp.com'))
        except ValueError:
            return Response({"detail": "Backend URL is misconfigured."}, status=400)
        folder = Path(__file__).resolve().parent.parent / 'static' / 'discord_bridge'
        names = ('bridge.py', 'backend_url.py', 'requirements.txt', 'README.txt', 'Setup_Guide.pdf', 'Commands_Guide.pdf')
        if any(not (folder / name).is_file() for name in names):
            return Response({"detail": "Discord bridge files unavailable."}, status=503)
        with transaction.atomic():
            integration, secret = issue_discord_integration(request.user, bot)
            env_text = (f'DISCORD_TOKEN={token}\nDJANGO_API_TOKEN={secret}\n'
                        f'DJANGO_BOT_ID={bot.id}\nDJANGO_BACKEND={backend}\n')
            archive = io.BytesIO()
            with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zf:
                for name in names:
                    zf.write(folder / name, arcname=f'discord_bridge/{name}')
                zf.writestr('discord_bridge/.env', env_text)
        response = Response({"filename": "discord_bridge.zip", "zip_base64": base64.b64encode(archive.getvalue()).decode('ascii'), "integration_id": integration.pk})
        response['Cache-Control'] = 'no-store, private'
        response['Pragma'] = 'no-cache'
        return response

class NativeDiscordRevokeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, bot_id, integration_id):
        bot = get_object_or_404(Bot, pk=bot_id, owner=request.user)
        integration = get_object_or_404(DiscordIntegration, pk=integration_id, bot=bot, owner=request.user)
        DiscordIntegration.objects.filter(pk=integration.pk, revoked_at__isnull=True).update(revoked_at=timezone.now())
        return Response({"message": "Discord integration revoked."})
