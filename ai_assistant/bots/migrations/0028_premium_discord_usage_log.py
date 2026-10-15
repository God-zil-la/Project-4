from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("bots", "0027_premium_discord_guild"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PremiumDiscordUsageLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("input_tokens", models.PositiveIntegerField(default=0)),
                ("output_tokens", models.PositiveIntegerField(default=0)),
                ("model", models.CharField(max_length=100)),
                ("timestamp", models.DateTimeField(auto_now_add=True)),
                ("guild", models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="usage_logs", to="bots.premiumdiscordguild")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="premium_discord_usage_logs", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
