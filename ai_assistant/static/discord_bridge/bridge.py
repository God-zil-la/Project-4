import discord, os, requests, random
from dotenv import load_dotenv
from discord.ext import commands

load_dotenv()
TOKEN        = os.getenv("DISCORD_TOKEN")
DJANGO_TOKEN = os.getenv("DJANGO_API_TOKEN")
BOT_ID       = os.getenv("DJANGO_BOT_ID")
BACKEND      = "https://ai-assistants-8c06fcfeab86.herokuapp.com"
API_URL      = f"{BACKEND}/bots/api/bot/{BOT_ID}/chat/"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.event
async def on_message(msg):
    if msg.author == bot.user:
        return
    if any(g in msg.content.lower() for g in ["hi", "hello", "hey"]):
        await msg.channel.send(random.choice(["Hi!", "Hey!", "Hello!"]))
        return

    r = requests.post(
        API_URL,
        headers={"Authorization": f"Token {DJANGO_TOKEN}"},
        json={"message": msg.content},
        timeout=30,
    )
    reply = r.json().get("response", "⚠️ error")
    await msg.channel.send(reply)

@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

bot.run(TOKEN)
