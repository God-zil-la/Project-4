"""
Discord Bot Integration with OpenAI GPT-3.5 Turbo.

Features:
- Responds to any user message using OpenAI Chat API
- Tracks user message history for contextual replies
- Includes simple bot commands (ping, hello)
- Requires DISCORD_TOKEN and OPENAI_API_KEY in .env
"""

import os
import logging
import discord
import openai
from dotenv import load_dotenv
from discord.ext import commands

# Load environment variables
load_dotenv()

# Required credentials
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DISCORD_TOKEN or not OPENAI_API_KEY:
    raise ValueError("Error: Missing DISCORD_TOKEN or OPENAI_API_KEY in .env file.")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize OpenAI
openai.api_key = OPENAI_API_KEY

# Discord bot setup
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Store conversation history by user ID
user_conversations = {}


@bot.event
async def on_ready():
    """
    Called when the bot is ready and connected.
    """
    logger.info(f"✅ Logged in as {bot.user}")


@bot.event
async def on_message(message):
    """
    Handle incoming Discord messages (excluding bot's own).

    - Appends user message to conversation history
    - Sends message history to OpenAI
    - Responds with assistant's reply
    - Catches and reports API and general errors
    """
    if message.author == bot.user:
        return  # Ignore bot's own messages

    logger.info(f"📥 Message from {message.author}: {message.content}")

    await bot.process_commands(message)  # Allow commands like !ping

    user_id = message.author.id
    history = user_conversations.get(user_id, [])
    history.append({"role": "user", "content": message.content})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=history,
            max_tokens=150
        )

        bot_reply = response.choices[0].message.content.strip()
        history.append({"role": "assistant", "content": bot_reply})
        user_conversations[user_id] = history

        await message.channel.send(bot_reply)

    except openai.error.OpenAIError as e:
        logger.error(f"OpenAI API error: {e}")
        await message.channel.send("⚠️ Sorry, there was a problem reaching the AI service.")

    except Exception as e:
        logger.error(f"General error: {e}")
        await message.channel.send("⚠️ An unexpected error occurred. Please try again.")


@bot.command()
async def ping(ctx):
    """
    Command: !ping
    Purpose: Check if the bot is online.
    """
    await ctx.send("🏓 Pong!")


@bot.command()
async def hello(ctx):
    """
    Command: !hello
    Purpose: Send a personalized greeting to the user.
    """
    await ctx.send(f"👋 Hello, {ctx.author.display_name}!")


# Start the bot
bot.run(DISCORD_TOKEN)
