"""Protect username uniqueness, including simultaneous registrations.

The index belongs to Django's built-in auth.User table. Manage it explicitly
here rather than modifying Django's migrations or replacing the user model.
"""
from django.db import migrations, models
from django.db.models import Count
from django.db.models.functions import Upper


INDEX_NAME = "accounts_user_username_ci_unique"


def username_constraint():
    # Matches PostgreSQL's username__iexact lookup; SQLite UPPER is ASCII-only.
    return models.UniqueConstraint(Upper("username"), name=INDEX_NAME)


def add_index(apps, schema_editor):
    user = apps.get_model("auth", "User")
    collisions = (
        user.objects.using(schema_editor.connection.alias)
        .annotate(username_ci=Upper("username"))
        .values("username_ci")
        .annotate(total=Count("pk"))
        .filter(total__gt=1)
    )
    if collisions.exists():
        raise RuntimeError(
            "Case-insensitive username collisions exist. Resolve the conflicting "
            "accounts with their owners before retrying this migration. "
            "No usernames have been changed."
        )
    schema_editor.add_constraint(user, username_constraint())


def remove_index(apps, schema_editor):
    schema_editor.remove_constraint(apps.get_model("auth", "User"), username_constraint())


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_userprofile_complimentary_plan_and_more"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [migrations.RunPython(add_index, remove_index)]
