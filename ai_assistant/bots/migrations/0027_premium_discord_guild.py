from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("bots", "0026_discord_conversation_scope"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PremiumDiscordGuild",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("guild_id", models.CharField(max_length=32, unique=True)),
                ("guild_name", models.CharField(blank=True, max_length=100)),
                ("connected_at", models.DateTimeField(auto_now_add=True)),
                ("disconnected_at", models.DateTimeField(blank=True, null=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="premium_discord_guilds", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-connected_at",),
                "indexes": [models.Index(fields=["owner", "disconnected_at"], name="premium_guild_owner_active_idx")],
            },
        ),
    ]
