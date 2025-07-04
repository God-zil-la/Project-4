import discord
import os
import openai
import logging
from dotenv import load_dotenv
from discord.ext import commands

# --------------------------------------------------------
# Load environment variables from .env
# --------------------------------------------------------
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not DISCORD_TOKEN or not OPENAI_API_KEY:
    raise ValueError("Error: Missing DISCORD_TOKEN or OPENAI_API_KEY in .env file.")

# --------------------------------------------------------
# Configure OpenAI
# --------------------------------------------------------
openai.api_key = OPENAI_API_KEY

# --------------------------------------------------------
# Setup logging
# --------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------------------------------------
# Setup Discord Bot
# --------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# --------------------------------------------------------
# Per-user conversation memory
# --------------------------------------------------------
user_conversations = {}

# --------------------------------------------------------
# Events
# --------------------------------------------------------
@bot.event
async def on_ready():
    logger.info(f"✅ Logged in as {bot.user}")

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Log received message
    logger.info(f"📥 Message from {message.author}: {message.content}")

    # Check if it's a command (needed so @bot.command() works)
    await bot.process_commands(message)

    # Free-form chat: respond to any message
    user_id = message.author.id
    history = user_conversations.get(user_id, [])

    history.append({"role": "user", "content": message.content})

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # Or "gpt-4" if you have access
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

# --------------------------------------------------------
# Commands
# --------------------------------------------------------
@bot.command()
async def ping(ctx):
    """Check if the bot is online."""
    await ctx.send("🏓 Pong!")

@bot.command()
async def hello(ctx):
    """Simple friendly greeting."""
    await ctx.send(f"👋 Hello, {ctx.author.display_name}!")

# --------------------------------------------------------
# Run the bot
# --------------------------------------------------------
bot.run(DISCORD_TOKEN)
