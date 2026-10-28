import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='STTAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lock_version', models.PositiveBigIntegerField(default=0)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='STTPeriod',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('starts_at', models.DateTimeField()),
                ('ends_at', models.DateTimeField()),
                ('verification_ref', models.CharField(max_length=160)),
                ('used_ms', models.PositiveBigIntegerField(default=0)),
                ('reserved_ms', models.PositiveBigIntegerField(default=0)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='u6_stt.sttaccount')),
            ],
        ),
        migrations.CreateModel(
            name='STTReservation',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('request_id', models.UUIDField()),
                ('duration_ms', models.PositiveBigIntegerField()),
                ('state', models.CharField(default='reserved', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('account', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='u6_stt.sttaccount')),
                ('period', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='u6_stt.sttperiod')),
            ],
        ),
        migrations.AddConstraint(
            model_name='sttperiod',
            constraint=models.UniqueConstraint(fields=('account', 'starts_at', 'ends_at'), name='stt_unique_period'),
        ),
        migrations.AddConstraint(
            model_name='sttperiod',
            constraint=models.CheckConstraint(condition=models.Q(('ends_at__gt', models.F('starts_at'))), name='stt_valid_period'),
        ),
        migrations.AddConstraint(
            model_name='sttperiod',
            constraint=models.CheckConstraint(condition=models.Q(('used_ms__gte', 0), ('reserved_ms__gte', 0)), name='stt_nonnegative_usage'),
        ),
        migrations.AddConstraint(
            model_name='sttreservation',
            constraint=models.UniqueConstraint(fields=('account', 'request_id'), name='stt_idempotent_request'),
        ),
        migrations.AddConstraint(
            model_name='sttreservation',
            constraint=models.CheckConstraint(condition=models.Q(('duration_ms__gt', 0)), name='stt_positive_duration'),
        ),
        migrations.AddConstraint(
            model_name='sttreservation',
            constraint=models.CheckConstraint(condition=models.Q(('state__in', ['reserved', 'dispatched', 'uncertain', 'consumed', 'released'])), name='stt_valid_state'),
        ),
    ]
