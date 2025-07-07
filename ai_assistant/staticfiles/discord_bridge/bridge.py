import os
import discord
import requests
import random
from dotenv import load_dotenv
from discord.ext import commands

# ------------------------------------
# Load environment variables from .env
# ------------------------------------
load_dotenv()
TOKEN        = os.getenv("DISCORD_TOKEN")
DJANGO_TOKEN = os.getenv("DJANGO_API_TOKEN")
BOT_ID       = os.getenv("DJANGO_BOT_ID")

if not TOKEN or not DJANGO_TOKEN or not BOT_ID:
    raise ValueError("❌ Missing environment variables! Please check your .env file.")

# ------------------------------------
# Django API endpoint
# ------------------------------------
BACKEND  = "https://ai-assistants-8c06fcfeab86.herokuapp.com"
API_URL  = f"{BACKEND}/bots/api/bot/{BOT_ID}/chat/"

# ------------------------------------
# Set up Discord bot
# ------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ------------------------------------
# Event: Bot is ready
# ------------------------------------
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")

# ------------------------------------
# Event: On message
# ------------------------------------
@bot.event
async def on_message(msg):
    if msg.author == bot.user:
        return

    # Simple hard-coded greeting response
    if any(greet in msg.content.lower() for greet in ["hi", "hello", "hey"]):
        await msg.channel.send(random.choice(["Hi!", "Hey!", "Hello!"]))
        return

    # Forward message to AI backend
    try:
        r = requests.post(
            API_URL,
            headers={"Authorization": f"Token {DJANGO_TOKEN}"},
            json={"message": msg.content},
            timeout=30,
        )
        r.raise_for_status()
        reply = r.json().get("response", "⚠️ No response from AI service.")
    except Exception as e:
        print(f"[ERROR] {e}")
        reply = "⚠️ Sorry, couldn't reach AI service. Please try again."

    await msg.channel.send(reply)

# ------------------------------------
# Command: !ping
# ------------------------------------
@bot.command()
async def ping(ctx):
    await ctx.send("🏓 Pong!")

# ------------------------------------
# Run the bot
# ------------------------------------
bot.run(TOKEN)
