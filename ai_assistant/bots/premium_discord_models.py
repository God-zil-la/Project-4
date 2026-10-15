"""Isolated Premium Discord guild records (no Pro DiscordIntegration changes)."""
from django.conf import settings
from django.db import models


class PremiumDiscordGuild(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="premium_discord_guilds",
    )
    guild_id = models.CharField(max_length=32, unique=True)
    guild_name = models.CharField(max_length=100, blank=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    disconnected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-connected_at",)
        indexes = [models.Index(fields=["owner", "disconnected_at"], name="premium_guild_owner_active_idx")]

    @property
    def is_connected(self):
        return self.disconnected_at is None

    def __str__(self):
        return f"Premium Discord guild {self.guild_id}"


class PremiumDiscordUsageLog(models.Model):
    """Cost accounting without inventing a customer Bot or modifying Pro usage logs."""
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="premium_discord_usage_logs",
    )
    guild = models.ForeignKey(
        PremiumDiscordGuild, on_delete=models.SET_NULL, null=True,
        related_name="usage_logs",
    )
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    model = models.CharField(max_length=100)
    timestamp = models.DateTimeField(auto_now_add=True)


class PremiumDiscordJob(models.Model):
    """Durable queue item; interaction token is encrypted, never stored as plaintext."""
    interaction_id = models.CharField(max_length=32, unique=True)
    guild_id = models.CharField(max_length=32)
    application_id = models.CharField(max_length=32)
    encrypted_token = models.TextField()
    prompt = models.TextField()
    status = models.CharField(max_length=16, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
