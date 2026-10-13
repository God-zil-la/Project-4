from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("bots", "0025_discord_integration")]
    operations = [migrations.AddField(
        model_name="conversation", name="discord_integration",
        field=models.ForeignKey(
            to="bots.discordintegration", null=True, blank=True, editable=False,
            on_delete=django.db.models.deletion.SET_NULL, related_name="conversations",
        ),
    )]
