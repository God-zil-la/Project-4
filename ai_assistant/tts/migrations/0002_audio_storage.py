"""Durable U6.2 cleanup/budget tables; isolated migration, not deployed."""
from django.db import migrations


def create_storage_tables(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    statements = (
        """CREATE TABLE tts_audio_cleanup (
            request_id UUID PRIMARY KEY,
            account_id BIGINT NOT NULL,
            size_bytes BIGINT NOT NULL CHECK (size_bytes BETWEEN 1 AND 8388608),
            expires_at TIMESTAMPTZ NOT NULL,
            next_attempt_at TIMESTAMPTZ NOT NULL,
            lease_token UUID,
            lease_until TIMESTAMPTZ,
            retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CHECK ((lease_token IS NULL AND lease_until IS NULL) OR
                   (lease_token IS NOT NULL AND lease_until IS NOT NULL))
        )""",
        "CREATE INDEX tts_audio_cleanup_due_idx ON tts_audio_cleanup(next_attempt_at, lease_until)",
        """CREATE TABLE tts_audio_budget (
            scope TEXT PRIMARY KEY,
            bytes_reserved BIGINT NOT NULL DEFAULT 0 CHECK (bytes_reserved >= 0),
            objects_reserved INTEGER NOT NULL DEFAULT 0 CHECK (objects_reserved >= 0),
            uploads_today INTEGER NOT NULL DEFAULT 0 CHECK (uploads_today >= 0),
            usage_day DATE NOT NULL DEFAULT CURRENT_DATE
        )""",
    )
    with schema_editor.connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)


def drop_storage_tables(apps, schema_editor):
    if schema_editor.connection.vendor != 'postgresql':
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('DROP TABLE tts_audio_cleanup')
        cursor.execute('DROP TABLE tts_audio_budget')


class Migration(migrations.Migration):
    dependencies = [('u62_tts', '0001_initial')]
    operations = [migrations.RunPython(create_storage_tables, reverse_code=drop_storage_tables)]
