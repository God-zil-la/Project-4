"""AI Assistant Discord bridge (Python 3.13, discord.py 2.x).

Run: pip install -r requirements.txt; then python bridge.py.
Place .env beside this file. Enable Message Content Intent in the Discord
Developer Portal (Bot -> Privileged Gateway Intents). Invite the bot with
View Channels, Send Messages and, for threads, Send Messages in Threads.
Triggers: !ask <question>, a direct bot mention plus question, or DM text.
!ping checks Discord connectivity without an AI request.

History is separate per channel/thread/DM for this process lifetime. Restarting
starts fresh conversations; one running bridge instance per installation is
recommended. Users in a shared channel share that channel's conversation.
The selected assistant's Knowledge Base is available to those users.
Never post .env, downloaded ZIPs or credentials in Discord or logs.
"""
import asyncio
import os
import re
from pathlib import Path
from uuid import UUID

import discord
import requests
from discord.ext import commands
from dotenv import load_dotenv

if __package__:
    from .backend_url import normalize_backend_url
else:
    from backend_url import normalize_backend_url


class BridgeError(Exception):
    """Only fixed, non-sensitive user messages are used here."""


def load_config():
    load_dotenv(Path(__file__).with_name(".env"))
    names = ("DISCORD_TOKEN", "DJANGO_API_TOKEN", "DJANGO_BOT_ID", "DJANGO_BACKEND")
    config = {name: os.getenv(name, "").strip() for name in names}
    if any(not value or any(ord(c) < 32 for c in value) for value in config.values()):
        raise ValueError("Missing or invalid bridge configuration. Check the four .env settings.")
    if not re.fullmatch(r"[1-9][0-9]{0,18}", config["DJANGO_BOT_ID"]):
        raise ValueError("DJANGO_BOT_ID must be a positive integer.")
    config["DJANGO_BACKEND"] = normalize_backend_url(config["DJANGO_BACKEND"])
    return config


def request_ai(config, message, conversation_id=None):
    url = f"{config['DJANGO_BACKEND']}/bots/api/discord/bot/{config['DJANGO_BOT_ID']}/chat/"
    payload = {"message": message}
    if conversation_id is not None:
        payload["conversation_id"] = conversation_id
    response = None
    try:
        response = requests.post(
            url, headers={"Authorization": f"Discord {config['DJANGO_API_TOKEN']}"},
            json=payload, timeout=(5, 60), allow_redirects=False,
        )
        messages = {
            401: "Discord integration access is invalid or revoked. Ask the owner to reconnect.",
            403: "Discord access requires Pro and available usage quota. Ask the owner to check access.",
            404: "The configured assistant is unavailable. Ask the owner to check the integration.",
            429: "Too many requests. Wait before sending another message.",
        }
        if response.status_code != 200:
            raise BridgeError(messages.get(response.status_code, "AI service request failed. Try again later."))
        try:
            data = response.json()
            if (not isinstance(data, dict) or not isinstance(data.get("response"), str)
                    or not data["response"].strip() or not isinstance(data.get("conversation_id"), str)):
                raise ValueError
            returned_id = str(UUID(data["conversation_id"]))
            if conversation_id is not None and returned_id != conversation_id:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise BridgeError("AI service returned an invalid response. Try again later.") from None
        return data["response"], returned_id
    except requests.Timeout:
        raise BridgeError("AI service timed out. No automatic retry was sent.") from None
    except requests.RequestException:
        raise BridgeError("AI service could not be reached. Try again later.") from None
    finally:
        if response is not None:
            response.close()


def split_reply(text):
    # UTF-16 units are conservative for Discord's 2,000-character limit.
    chunk = []
    size = 0
    for char in text:
        units = 2 if ord(char) > 0xFFFF else 1
        if size + units > 2000:
            yield "".join(chunk)
            chunk, size = [], 0
        chunk.append(char)
        size += units
    if chunk:
        yield "".join(chunk)


async def send_reply(channel, text):
    try:
        for chunk in split_reply(text):
            await channel.send(chunk, allowed_mentions=discord.AllowedMentions.none())
    except (discord.HTTPException, OSError):
        print("[ERROR] Unable to send a Discord reply. Check channel permissions and connectivity.")


class ConversationState:
    def __init__(self):
        self.conversations = {}
        self.locks = {}

    async def answer(self, config, context, message):
        lock = self.locks.setdefault(context, asyncio.Lock())
        # Serialize messages within a context; different channels can run concurrently.
        async with lock:
            current_id = self.conversations.get(context)
            reply, returned_id = await asyncio.to_thread(request_ai, config, message, current_id)
            if any(key != context and value == returned_id for key, value in self.conversations.items()):
                raise BridgeError("AI service returned a conflicting conversation. Ask the owner to check the integration.")
            self.conversations[context] = returned_id
            return reply


def create_bot(config):
    intents = discord.Intents.default()
    intents.message_content = True
    bot = commands.Bot(command_prefix="!", intents=intents, allowed_mentions=discord.AllowedMentions.none())
    state = ConversationState()

    @bot.event
    async def on_ready():
        print("Discord bridge connected.")

    @bot.command()
    async def ping(ctx):
        await send_reply(ctx.channel, "🏓 Pong!")

    @bot.event
    async def on_message(message):
        if message.author.bot or message.author == bot.user:
            return
        content = message.content.strip()
        if content == "!ping":
            await bot.process_commands(message)
            return
        parts = content.split(maxsplit=1)
        if parts and parts[0] == "!ask":
            prompt = parts[1] if len(parts) == 2 else ""
        elif bot.user and re.search(rf"<@!?{bot.user.id}>", content):
            prompt = re.sub(rf"<@!?{bot.user.id}>", "", content).strip()
        elif message.guild is None:
            prompt = content
        else:
            return
        if not prompt:
            await send_reply(message.channel, "Use !ask followed by your question, or mention me with a question.")
            return
        context = (message.guild.id if message.guild else None, message.channel.id)
        try:
            reply = await state.answer(config, context, prompt)
        except BridgeError as error:
            reply = str(error)
        except Exception:
            # Never print response bodies, requests, configuration or raw exceptions.
            reply = "AI service request failed. Try again later."
        await send_reply(message.channel, reply)

    return bot


def main():
    try:
        config = load_config()
        create_bot(config).run(config["DISCORD_TOKEN"], log_handler=None)
    except Exception:
        print("[ERROR] Bridge stopped. Check configuration, credentials and Discord intents.")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
