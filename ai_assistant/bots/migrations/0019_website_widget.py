from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('bots', '0018_assistant_customization')]
    operations = [
        migrations.AddField(model_name='bot', name='widget_enabled', field=models.BooleanField(default=False)),
        migrations.AddField(model_name='bot', name='widget_public_id', field=models.UUIDField(blank=True, editable=False, null=True, unique=True)),
        migrations.AddField(model_name='conversation', name='is_widget', field=models.BooleanField(default=False, editable=False)),
    ]
