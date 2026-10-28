from django.db import migrations, models
from django.db.models import F, Q
from django.db.migrations.exceptions import IrreversibleError


def preserve_existing_charges(apps, schema_editor):
    # Existing counters reflect measured milliseconds. Never retroactively round
    # old holds or usage; settlement must subtract exactly what was reserved.
    reservations = apps.get_model('u6_stt', 'STTReservation')
    reservations.objects.using(schema_editor.connection.alias).update(charge_ms=F('duration_ms'))


def guard_reverse(apps, schema_editor):
    reservations = apps.get_model('u6_stt', 'STTReservation')
    if reservations.objects.using(schema_editor.connection.alias).exclude(charge_ms=F('duration_ms')).exists():
        raise IrreversibleError('Rounded STT charges require the new ledger; rollback refused')


class Migration(migrations.Migration):
    dependencies = [('u6_stt', '0002_sttperiodbinding')]
    operations = [
        migrations.AddField(model_name='sttreservation', name='charge_ms',
                            field=models.PositiveBigIntegerField(null=True)),
        # Old code cannot safely settle rounded holds.
        migrations.RunPython(preserve_existing_charges, guard_reverse),
        migrations.AlterField(model_name='sttreservation', name='charge_ms',
                              field=models.PositiveBigIntegerField()),
        migrations.AddConstraint(model_name='sttreservation',
            constraint=models.CheckConstraint(condition=Q(charge_ms__gt=0), name='stt_positive_charge')),
    ]
