"""General Premium Discord AI; never loads a customer's Bot, KB or instructions."""
import logging

import openai
from django.core.cache import cache

from ai_assistant.accounts.plan_utils import get_ai_usage_status
from .chat_service import CHAT_MODEL, _check_rate_limit
from .premium_discord_guild_service import resolve_active_premium_guild

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are AI Assistant, a general-purpose assistant in a public Discord server. "
    "Answer clearly and helpfully in the user's language. You have no access to "
    "account-specific assistants, private conversations, uploaded files, or personal data. "
    "Do not claim to have such access."
)


class PremiumDiscordChatError(ValueError):
    pass


def answer_premium_discord(*, guild_id, message):
    if not isinstance(message, str) or not message.strip() or len(message) > 2000:
        raise PremiumDiscordChatError("Message must contain 1–2,000 characters.")
    guild = resolve_active_premium_guild(guild_id)
    if guild is None:
        raise PremiumDiscordChatError("This server is not connected to an active Premium account.")
    owner = guild.owner
    profile = owner.profile
    # Shared per-account rate limiting: Discord must not bypass web/mobile.
    _check_rate_limit(owner, profile)
    usage = get_ai_usage_status(owner)
    if not usage["allowed"]:
        raise PremiumDiscordChatError("The account's monthly AI usage limit has been reached.")
    reservation = profile.reserve_message_slot(usage["monthly_message_limit"])
    if reservation is None:
        raise PremiumDiscordChatError("The account's monthly message limit has been reached.")
    try:
        response = openai.ChatCompletion.create(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": message.strip()},
            ],
            max_tokens=600,
            request_timeout=20,
        )
        answer = (response.choices[0].message.get("content") or "").strip()
        if not answer:
            raise PremiumDiscordChatError("AI did not return an answer.")
        return answer[:1900]
    except Exception:
        profile.release_message_slot(reservation)
        logger.exception("Premium Discord general AI request failed")
        raise
