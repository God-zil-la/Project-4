from .models import Bot


def sidebar_assistants(request):
    """Provide the current user's assistants to the navigation."""
    if not request.user.is_authenticated:
        return {"sidebar_bots": []}

    return {
        "sidebar_bots": Bot.objects.filter(
            owner=request.user
        ).order_by("name")
    }
