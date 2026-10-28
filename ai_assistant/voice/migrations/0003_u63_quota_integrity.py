from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def backfill_reservations(apps, schema_editor):
    Reservation = apps.get_model("u63_voice", "LiveVoiceQuotaReservation")

    for reservation in Reservation.objects.select_related("usage").iterator():
        reservation.user_id = reservation.usage.user_id

        if reservation.state == "committed":
            raise RuntimeError(
                "Existing committed reservations need audited charge backfill"
            )

        reservation.save(update_fields=["user"])


class Migration(migrations.Migration):
    dependencies = [
        ("u63_voice", "0002_u63_live_voice_monthly_quota"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="livevoicequotareservation",
            name="charged_ms",
            field=models.PositiveBigIntegerField(
                null=True, blank=True
            ),
        ),
        migrations.AddField(
            model_name="livevoicequotareservation",
            name="user",
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL,
                on_delete=django.db.models.deletion.CASCADE,
                null=True,
                blank=True,
            ),
        ),
        migrations.RunPython(
            backfill_reservations,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="livevoicequotareservation",
            constraint=models.UniqueConstraint(
                fields=("user", "request_id"),
                name="u63_unique_user_request",
            ),
        ),
    ]