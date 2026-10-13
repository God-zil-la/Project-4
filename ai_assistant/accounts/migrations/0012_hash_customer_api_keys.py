import hashlib
import secrets

from django.db import migrations, models


def hash_existing_keys(apps, schema_editor):
    Profile = apps.get_model("accounts", "UserProfile")
    database = schema_editor.connection.alias
    for profile in Profile.objects.using(database).all().iterator():
        secret = profile.api_key or secrets.token_hex(32)
        digest = "sha256$" + hashlib.sha256(secret.encode("utf-8")).hexdigest()
        Profile.objects.using(database).filter(pk=profile.pk).update(api_key=digest)


def invalidate_keys_on_rollback(apps, schema_editor):
    # Hashes cannot be decrypted. Rollback explicitly revokes customer keys.
    Profile = apps.get_model("accounts", "UserProfile")
    database = schema_editor.connection.alias
    for profile in Profile.objects.using(database).all().iterator():
        Profile.objects.using(database).filter(pk=profile.pk).update(
            api_key=secrets.token_hex(32),
        )


class Migration(migrations.Migration):
    dependencies = [("accounts", "0011_unique_username_case_insensitive")]
    operations = [
        migrations.AlterField(
            model_name="userprofile", name="api_key",
            field=models.CharField(blank=True, max_length=71, unique=True),
        ),
        migrations.RunPython(hash_existing_keys, invalidate_keys_on_rollback),
    ]
