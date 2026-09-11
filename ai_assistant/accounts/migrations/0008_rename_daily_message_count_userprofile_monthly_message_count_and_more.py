import ai_assistant.accounts.models
from django.db import migrations, models


def reset_message_counter(apps, schema_editor):
    UserProfile = apps.get_model("accounts", "UserProfile")

    UserProfile.objects.all().update(
        monthly_message_count=0,
    )


class Migration(migrations.Migration):

    dependencies = [
        (
            "accounts",
            "0007_userprofile_subscription_cancel_at_period_end_and_more",
        ),
    ]

    operations = [
        migrations.RenameField(
            model_name="userprofile",
            old_name="daily_message_count",
            new_name="monthly_message_count",
        ),
        migrations.RemoveField(
            model_name="userprofile",
            name="last_reset",
        ),
        migrations.AddField(
            model_name="userprofile",
            name="message_count_period_start",
            field=models.DateField(
                default=ai_assistant.accounts.models.current_month_start,
            ),
        ),
        migrations.RunPython(
            reset_message_counter,
            migrations.RunPython.noop,
        ),
    ]