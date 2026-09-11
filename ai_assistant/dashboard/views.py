from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.utils import timezone

from ai_assistant.bots.models import Bot, ChatMessage, KnowledgeBase


def home(request):
    """
    Public landing page.
    """
    return render(request, "dashboard/index.html")


@login_required
def dashboard(request):
    """
    Customer dashboard with real account usage.
    """
    user = request.user
    profile = user.profile
    plan = profile.effective_plan

    plan_limits = {
        "free": {
            "messages": 150,
            "bots": 1,
            "knowledge_bytes": 10 * 1024 * 1024,
            "knowledge_display": "10 MB",
        },
        "premium": {
            "messages": 3000,
            "bots": 5,
            "knowledge_bytes": 250 * 1024 * 1024,
            "knowledge_display": "250 MB",
        },
        "pro": {
            "messages": 10000,
            "bots": 15,
            "knowledge_bytes": 1024 * 1024 * 1024,
            "knowledge_display": "1 GB",
        },
    }

    limits = plan_limits.get(plan, plan_limits["free"])

    # Current UTC calendar month.
    now = timezone.now()
    month_start = now.replace(
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    # Count assistant responses generated for this user this month.
    message_count = ChatMessage.objects.filter(
        user=user,
        sender=ChatMessage.SENDER_ASSISTANT,
        timestamp__gte=month_start,
    ).count()

    # Count assistants owned by this user.
    bot_count = Bot.objects.filter(owner=user).count()

    # Calculate total Knowledge Base storage used by the user.
    knowledge_files = KnowledgeBase.objects.filter(
        bot__owner=user,
    )

    knowledge_bytes = 0

    for knowledge in knowledge_files:
        try:
            if knowledge.file:
                knowledge_bytes += knowledge.file.size
        except (OSError, FileNotFoundError, ValueError):
            # Ignore missing legacy files instead of breaking the dashboard.
            continue

    knowledge_mb = knowledge_bytes / (1024 * 1024)

    if knowledge_bytes >= 1024 * 1024 * 1024:
        knowledge_used_display = (
            f"{knowledge_bytes / (1024 * 1024 * 1024):.2f} GB"
        )
    else:
        knowledge_used_display = f"{knowledge_mb:.2f} MB"

    context = {
        "current_plan": plan,
        "message_count": message_count,
        "message_limit": limits["messages"],
        "bot_count": bot_count,
        "bot_limit": limits["bots"],
        "knowledge_used_display": knowledge_used_display,
        "knowledge_limit_display": limits["knowledge_display"],
    }

    return render(
        request,
        "dashboard/customer_dashboard.html",
        context,
    )


# Custom error triggers used for testing error pages.

def trigger_400(request):
    raise ValueError("Manually triggered 400")


def trigger_403(request):
    raise PermissionDenied("Manually triggered 403")


def trigger_500(request):
    raise Exception("Manually triggered 500")