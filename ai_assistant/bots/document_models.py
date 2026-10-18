import uuid

from django.conf import settings
from django.db import models


class GeneratedDocument(models.Model):
    """Persist ownership and storage location of a generated file."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="generated_documents",
    )

    bot = models.ForeignKey(
        "bots.Bot",
        on_delete=models.CASCADE,
        related_name="generated_documents",
    )

    conversation = models.ForeignKey(
        "bots.Conversation",
        on_delete=models.CASCADE,
        related_name="generated_documents",
    )

    object_key = models.CharField(
        max_length=255,
        unique=True,
    )

    filename = models.CharField(max_length=180)

    file_format = models.CharField(
        max_length=8,
        choices=[
            ("pdf", "PDF"),
            ("docx", "Word"),
            ("xlsx", "Excel"),
            ("csv", "CSV"),
        ],
    )

    size_bytes = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["owner", "conversation"],
                name="gen_doc_owner_conv_idx",
            ),
        ]

    def __str__(self):
        return self.filename
