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
TOKEN = os.getenv("DISCORD_TOKEN")
DJANGO_TOKEN = os.getenv("DJANGO_API_TOKEN")
BOT_ID = os.getenv("DJANGO_BOT_ID")

if not TOKEN or not DJANGO_TOKEN or not BOT_ID:
    raise ValueError("❌ Missing environment variables! Please check your .env file.")

# ------------------------------------
# Django API endpoint
# ------------------------------------
BACKEND = "https://ai-assistants-8c06fcfeab86.herokuapp.com"
API_URL = f"{BACKEND}/bots/api/bot/{BOT_ID}/chat/"

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
        print(f"➡️ Sending message to API: {msg.content}")
        r = requests.post(
            API_URL,
            headers={"Authorization": f"Token {DJANGO_TOKEN}"},
            json={"message": msg.content},
            timeout=30,
        )
        r.raise_for_status()
        reply = r.json().get("response", "⚠️ No response from AI service.")
        print(f"✅ AI response: {reply}")

    except requests.exceptions.HTTPError as http_err:
        status_code = http_err.response.status_code if http_err.response else "No Status"
        body = http_err.response.text if http_err.response else "No Body"
        print(f"[HTTP ERROR] Status: {status_code}")
        print(f"[HTTP ERROR] Body: {body}")
        reply = f"⚠️ Error {status_code}: Could not reach AI service."

    except requests.exceptions.RequestException as req_err:
        print(f"[REQUEST ERROR] {req_err}")
        reply = "⚠️ Sorry, couldn't connect to the AI service."

    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        reply = "⚠️ Sorry, an unexpected error occurred."

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
