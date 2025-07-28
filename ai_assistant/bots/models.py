"""
Models for managing bots, knowledge bases, chat messages, templates, and usage logs
in the AI Assistant platform.
"""

from django.db import models
from django.contrib.auth.models import User


class KnowledgeBase(models.Model):
    """
    Represents a file or manual input uploaded to a bot as a knowledge base.
    """
    bot = models.ForeignKey(
        'Bot',
        on_delete=models.CASCADE,
        related_name='knowledge_files',
        help_text="The bot this knowledge file belongs to."
    )
    file = models.FileField(
        upload_to='knowledge_files/',
        help_text="Uploaded document file used as bot knowledge."
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_files',
        help_text="User who uploaded the file (can be null if user is deleted)."
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp of when the file was uploaded."
    )

    def __str__(self):
        return f"{self.bot.name} - {self.file.name}"

    def get_chunks(self):
        return self.chunks.all()


class KnowledgeChunk(models.Model):
    """
    A chunk of text extracted from a KnowledgeBase file, used for embedding and retrieval.
    """
    knowledge_file = models.ForeignKey(
        KnowledgeBase,
        on_delete=models.CASCADE,
        related_name='chunks',
        help_text="The parent knowledge file this chunk belongs to."
    )
    text = models.TextField(
        help_text="The actual content of this chunk."
    )
    embedding = models.JSONField(
        null=True,
        blank=True,
        help_text="The vector embedding of this chunk for semantic search."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the chunk was created."
    )

    def __str__(self):
        return f"Chunk of {self.knowledge_file.file.name[:30]} ({len(self.text)} chars)"


class Bot(models.Model):
    """
    Represents a user-created AI bot with a defined personality and category.
    """
    CATEGORY_CHOICES = [
        ('art', 'Art'), ('business', 'Business'), ('career', 'Career'),
        ('community', 'Community'), ('culture', 'Culture'),
        ('current_affairs', 'Current Affairs'), ('education', 'Education'),
        ('entrepreneurship', 'Entrepreneurship'), ('entertainment', 'Entertainment'),
        ('environment', 'Environment'), ('events', 'Events'),
        ('fashion', 'Fashion'), ('finance', 'Finance'), ('fitness', 'Fitness'),
        ('food', 'Food'), ('funny', 'Funny'), ('gaming', 'Gaming'),
        ('gardening', 'Gardening'), ('general', 'General'), ('hobbies', 'Hobbies'),
        ('history', 'History'), ('home_improvement', 'Home Improvement'),
        ('innovation', 'Innovation'), ('interview_preparation', 'Interview Preparation'),
        ('job_search', 'Job Search'), ('language', 'Language'), ('leadership', 'Leadership'),
        ('lifestyle', 'Lifestyle'), ('local', 'Local'), ('management', 'Management'),
        ('marketing', 'Marketing'), ('mental_health', 'Mental Health'),
        ('music', 'Music'), ('news', 'News'), ('other', 'Other'),
        ('parenting', 'Parenting'), ('pets', 'Pets'), ('philosophy', 'Philosophy'),
        ('politics', 'Politics'), ('productivity', 'Productivity'),
        ('relationships', 'Relationships'), ('resume_building', 'Resume Building'),
        ('sales', 'Sales'), ('science', 'Science'), ('self_improvement', 'Self Improvement'),
        ('shopping', 'Shopping'), ('society', 'Society'), ('spirituality', 'Spirituality'),
        ('sports', 'Sports'), ('support', 'Support'), ('sustainability', 'Sustainability'),
        ('tech', 'Tech'), ('technology', 'Technology'), ('therapy', 'Therapy'),
        ('travel', 'Travel'), ('wellbeing', 'Wellbeing'), ('wellness', 'Wellness'),
        ('3-D Printing', '3-D Printing'),
    ]

    name = models.CharField(max_length=100, help_text="Name of the bot.")
    description = models.TextField(blank=True, help_text="Short description of the bot.")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, help_text="User who owns the bot.")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Creation timestamp.")
    personality = models.TextField(
        default="I am a helpful and friendly assistant.",
        help_text="Defines the assistant's tone and response style."
    )
    category = models.CharField(
        max_length=23,
        choices=CATEGORY_CHOICES,
        default='general',
        help_text="Thematic category that shapes bot behavior."
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'name'], name='unique_bot_per_user')
        ]

    def __str__(self):
        return self.name


class ChatMessage(models.Model):
    """
    Represents a single message exchanged between user and bot.
    """
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name='chat_messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField(help_text="Message content.")
    sender = models.CharField(
        max_length=10,
        choices=[('user', 'User'), ('bot', 'Bot')],
        help_text="Indicates whether the message was sent by the user or the bot."
    )
    timestamp = models.DateTimeField(auto_now_add=True, help_text="Timestamp of the message.")

    def __str__(self):
        return f"{self.sender}: {self.message[:50]}"


class BotTemplate(models.Model):
    """
    Represents a reusable bot template for quick creation.
    """
    name = models.CharField(max_length=100, help_text="Template name.")
    description = models.TextField(blank=True, help_text="Short description of the template.")
    personality = models.TextField(
        default="I am a helpful and friendly assistant.",
        help_text="Default personality used by bots created from this template."
    )
    category = models.CharField(
        max_length=23,
        choices=Bot.CATEGORY_CHOICES,
        default='general',
        help_text="Category to classify template bots."
    )

    def __str__(self):
        return self.name


class BotUsageLog(models.Model):
    """
    Tracks how many tokens a user used with a specific bot.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bots_bot_usage_logs')
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name='bots_bot_usage_logs')
    tokens_used = models.IntegerField(help_text="Total number of tokens used during the session.")
    timestamp = models.DateTimeField(auto_now_add=True, help_text="When this usage was recorded.")

    def __str__(self):
        return f"{self.user.username} used {self.tokens_used} tokens on {self.timestamp}"
