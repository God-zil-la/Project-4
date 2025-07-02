import discord
import os
import openai
from dotenv import load_dotenv
import random
from discord.ext import commands

# Load the token from the .env file
load_dotenv()

# Get the bot token and OpenAI API key from the environment variables
TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Set up OpenAI API key
openai.api_key = OPENAI_API_KEY

# Create an instance of Bot with a command prefix
intents = discord.Intents.default()
intents.message_content = True  # Enable the bot to read message content

bot = commands.Bot(command_prefix="!", intents=intents)

# Event when the bot has connected to Discord
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

# Event when the bot receives a message
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    print(f"Received message: {message.content}")

    # Handle greetings first
    greetings = ['hello', 'hi', 'hey', 'yo', 'hiya', 'greetings']
    response_dict = {
        'hello': ["Hello!", "Hi there!", "Hey, how's it going?", "Hello, {}!"],
        'hi': ["Hi!", "Hey there!", "Hello!"],
        'hey': ["Hey!", "Hi! What's up?", "Hey, how's it going?"],
        'yo': ["Yo!", "What's up?", "Yo, what's good?"],
        'hiya': ["Hiya!", "Heyya!", "Howdy!"],
        'greetings': ["Greetings!", "Salutations!", "Hello, friend!"]
    }

    # If the message is a greeting, respond and return immediately
    for greeting in greetings:
        if greeting in message.content.lower():  # Substring match for flexibility
            response = random.choice(response_dict[greeting])
            await message.channel.send(response.format(message.author.name))
            return  # Stop further processing if it's a greeting

    # Handle bot commands (e.g., !hello, !ping)
    await bot.process_commands(message)

    # If the message doesn't start with a command and isn't a greeting, call OpenAI
    if not message.content.startswith("!"):
        prompt = f"The user said: '{message.content}'. Please provide a friendly, helpful, and context-aware response."

        try:
            # Make OpenAI API call using the ChatCompletion endpoint
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # Specify the model (GPT-3.5 or GPT-4 if available)
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150
            )

            # Log the full OpenAI API response for debugging
            print("OpenAI Response:", response)

            # Extract the response from OpenAI's API response
            bot_response = response['choices'][0]['message']['content']
            await message.channel.send(bot_response)

        except openai.error.OpenAIError as e:
            # Handle OpenAI-specific errors
            await message.channel.send("Sorry, I encountered an issue with OpenAI. Please try again later.")
            print(f"OpenAI API error: {e}")

        except Exception as e:
            # Handle any other unexpected errors
            await message.channel.send("An unexpected error occurred. Please try again.")
            print(f"General error: {e}")

# Respond to '!hello' using the commands extension
@bot.command()
async def hello(ctx):
    await ctx.send("Hello from the bot!")

# Respond to '!ping' using the commands extension
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

# Run the bot using the token from .env
bot.run(TOKEN)
