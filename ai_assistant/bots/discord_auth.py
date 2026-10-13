"""Credentials accepted only by the Discord chat route."""
import hashlib
import re
import secrets

from django.views.decorators.debug import sensitive_variables
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .models import DiscordIntegration


@sensitive_variables()
def issue_discord_integration(owner, bot):
    if not owner.is_active or bot.owner_id != owner.pk or not owner.profile.is_pro:
        raise AuthenticationFailed("Discord integration is unavailable.")
    secret = "dsc_" + secrets.token_hex(32)
    integration = DiscordIntegration.objects.create(
        owner=owner, bot=bot,
        secret_hash=hashlib.sha256(secret.encode("ascii")).hexdigest(),
    )
    return integration, secret


class DiscordIntegrationAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        return "Discord"

    @sensitive_variables()
    def authenticate(self, request):
        parts = get_authorization_header(request).split()
        if len(parts) != 2 or parts[0].lower() != b"discord":
            raise AuthenticationFailed("Discord integration credentials required.")
        secret = parts[1]
        if not re.fullmatch(rb"dsc_[0-9a-f]{64}", secret):
            raise AuthenticationFailed("Invalid Discord integration credentials.")
        digest = hashlib.sha256(secret).hexdigest()
        integration = (DiscordIntegration.objects.select_related("owner", "bot")
                       .filter(secret_hash=digest, revoked_at__isnull=True).first())
        bot_id = request.parser_context["kwargs"].get("bot_id")
        if (integration is None or not integration.owner.is_active
                or integration.bot_id != bot_id
                or integration.bot.owner_id != integration.owner_id):
            raise AuthenticationFailed("Invalid Discord integration credentials.")
        # The shared handler enforces current profile.is_pro before AI/quota work.
        return integration.owner, integration
