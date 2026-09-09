"""Monthly subscription prices in USD cents, shared by checkout and webhooks."""
from ai_assistant.accounts.models import UserProfile

CURRENCY = "usd"
PLAN_CONFIG = {
    UserProfile.PLAN_PREMIUM: {
        "name": "AI Assistant Premium",
        "unit_amount": 1299,
    },
    UserProfile.PLAN_PRO: {
        "name": "AI Assistant Pro",
        "unit_amount": 2499,
    },
}
