from django.db import models
from django.contrib.auth.models import User


class Bot(models.Model):
    CATEGORY_CHOICES = [
        ('art', 'Art'),
        ('business', 'Business'),
        ('career', 'Career'),
        ('community', 'Community'),
        ('culture', 'Culture'),
        ('current_affairs', 'Current Affairs'),
        ('education', 'Education'),
        ('entrepreneurship', 'Entrepreneurship'),
        ('entertainment', 'Entertainment'),
        ('environment', 'Environment'),
        ('events', 'Events'),
        ('fashion', 'Fashion'),
        ('finance', 'Finance'),
        ('fitness', 'Fitness'),
        ('food', 'Food'),
        ('funny', 'Funny'),
        ('gaming', 'Gaming'),
        ('gardening', 'Gardening'),
        ('general', 'General'),
        ('hobbies', 'Hobbies'),
        ('history', 'History'),
        ('home_improvement', 'Home Improvement'),
        ('innovation', 'Innovation'),
        ('interview_preparation', 'Interview Preparation'),
        ('job_search', 'Job Search'),
        ('language', 'Language'),
        ('leadership', 'Leadership'),
        ('lifestyle', 'Lifestyle'),
        ('local', 'Local'),
        ('management', 'Management'),
        ('marketing', 'Marketing'),
        ('mental_health', 'Mental Health'),
        ('music', 'Music'),
        ('news', 'News'),
        ('other', 'Other'),
        ('parenting', 'Parenting'),
        ('pets', 'Pets'),
        ('philosophy', 'Philosophy'),
        ('politics', 'Politics'),
        ('productivity', 'Productivity'),
        ('relationships', 'Relationships'),
        ('resume_building', 'Resume Building'),
        ('sales', 'Sales'),
        ('science', 'Science'),
        ('self_improvement', 'Self Improvement'),
        ('shopping', 'Shopping'),
        ('society', 'Society'),
        ('spirituality', 'Spirituality'),
        ('sports', 'Sports'),
        ('support', 'Support'),
        ('sustainability', 'Sustainability'),
        ('tech', 'Tech'),
        ('technology', 'Technology'),
        ('therapy', 'Therapy'),
        ('travel', 'Travel'),
        ('wellbeing', 'Wellbeing'),
        ('wellness', 'Wellness'),
        ('3-D Printing', '3-D Printing'),

    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    personality = models.TextField(default="I am a helpful and friendly assistant.")
    category = models.CharField(max_length=23, choices=CATEGORY_CHOICES, default='general')

    def __str__(self):
        return self.name


class ChatMessage(models.Model):
    bot = models.ForeignKey(Bot, on_delete=models.CASCADE, related_name='chat_messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    sender = models.CharField(max_length=10, choices=[('user', 'User'), ('bot', 'Bot')])
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender}: {self.message[:50]}"
