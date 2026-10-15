from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("bots", "0028_premium_discord_usage_log")]

    operations = [
        migrations.CreateModel(
            name="PremiumDiscordJob",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("interaction_id", models.CharField(max_length=32, unique=True)),
                ("guild_id", models.CharField(max_length=32)),
                ("application_id", models.CharField(max_length=32)),
                ("encrypted_token", models.TextField()),
                ("prompt", models.TextField()),
                ("status", models.CharField(default="pending", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
        ),
    ]
