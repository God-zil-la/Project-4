import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('bots', '0029_premium_discord_job'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name='GeneratedDocument', fields=[('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)), ('object_key', models.CharField(max_length=255, unique=True)), ('filename', models.CharField(max_length=180)), ('file_format', models.CharField(choices=[('pdf', 'PDF'), ('docx', 'Word'), ('xlsx', 'Excel'), ('csv', 'CSV')], max_length=8)), ('size_bytes', models.PositiveIntegerField()), ('created_at', models.DateTimeField(auto_now_add=True)), ('bot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='generated_documents', to='bots.bot')), ('conversation', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='generated_documents', to='bots.conversation')), ('owner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='generated_documents', to=settings.AUTH_USER_MODEL))], options={'ordering': ['-created_at'], 'indexes': [models.Index(fields=['owner', 'conversation'], name='gen_doc_owner_conv_idx')]})]
