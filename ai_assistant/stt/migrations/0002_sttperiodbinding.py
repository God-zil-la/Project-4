import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('u6_stt', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='STTPeriodBinding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('identity', models.CharField(max_length=64, unique=True)),
                ('plan', models.CharField(max_length=20)),
                ('period', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='u6_stt.sttperiod')),
            ],
        ),
    ]
