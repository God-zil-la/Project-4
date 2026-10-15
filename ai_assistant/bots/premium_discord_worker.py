"""Standalone Premium Discord queue processor. Run as a separate worker process."""
import logging
import time

import requests
from django.db import close_old_connections

from .premium_discord_chat import answer_premium_discord
from .premium_discord_queue import claim_interaction, decrypt_token, finish_interaction

logger = logging.getLogger(__name__)


def process_next():
    job = claim_interaction()
    if job is None:
        return False
    status = "failed"
    try:
        token = decrypt_token(job)
        try:
            answer = answer_premium_discord(guild_id=job.guild_id, message=job.prompt)
        except Exception:
            logger.exception("Premium Discord AI request failed")
            answer = "AI Assistant is unavailable or the account's usage limit was reached."
        response = requests.post(
            "https://discord.com/api/v10/webhooks/{}/{}".format(job.application_id, token),
            json={"content": answer[:1900], "allowed_mentions": {"parse": []}},
            timeout=10,
        )
        response.raise_for_status()
        status = "done"
    except Exception:
        logger.exception("Premium Discord job delivery failed")
    finally:
        finish_interaction(job, status)
    return True


def run_worker(*, poll_seconds=1):
    while True:
        close_old_connections()
        if not process_next():
            time.sleep(poll_seconds)
