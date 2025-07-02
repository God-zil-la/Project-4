import discord
import os
import openai
from dotenv import load_dotenv
import random

# Load the token from the .env file
load_dotenv()

# Get the bot token and OpenAI API key from the environment variables
TOKEN = os.getenv("DISCORD_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Set up OpenAI API key
openai.api_key = OPENAI_API_KEY

# Create an instance of Intents
intents = discord.Intents.default()
intents.message_content = True  # Enable the bot to read message content

# Create an instance of the bot with the intents
client = discord.Client(intents=intents)

# Event when the bot has connected to Discord
@client.event
async def on_ready():
    print(f'Logged in as {client.user}')

# Event when the bot receives a message
@client.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    print(f"Received message: {message.content}")  # Debugging log

    # List of greetings to check
    greetings = ['hello', 'hi', 'hey', 'yo', 'hiya', 'greetings']

    # Custom responses for different greetings
    response_dict = {
        'hello': ["Hello!", "Hi there!", "Hey, how's it going?", "Hello, [user]!"],
        'hi': ["Hi!", "Hey there!", "Hello!"],
        'hey': ["Hey!", "Hi! What's up?", "Hey, how's it going?"],
        'yo': ["Yo!", "What's up?", "Yo, what's good?"],
        'hiya': ["Hiya!", "Heyya!", "Howdy!"],
        'greetings': ["Greetings!", "Salutations!", "Hello, friend!"]
    }

    # Check if the message content matches any of the greetings exactly
    for greeting in greetings:
        if message.content.lower() == greeting:  # Ensure it's an exact match
            # Choose a random response from the response_dict
            response = random.choice(response_dict[greeting])
            await message.channel.send(response.replace("[user]", message.author.name))
            break

    # Respond to '!hello'
    if message.content.startswith('!hello'):
        await message.channel.send('Hello from the bot!')

    # Respond to '!ping'
    elif message.content.startswith('!ping'):
        await message.channel.send('Pong!')

    # Use OpenAI to respond to any other message
    else:
        prompt = f"The user said: {message.content}. Respond like a helpful assistant."
        try:
            # Log the model being used
            print("Using model: gpt-3.5-turbo")  # Log the model being used

            # Use the new OpenAI API method for creating a completion
            response = openai.Completion.create(
                model="gpt-3.5-turbo",  # Explicitly use gpt-3.5-turbo (or gpt-4 if you have access)
                prompt=prompt,
                max_tokens=150
            )

            # Log the full OpenAI API response for debugging
            print("OpenAI Response:", response)

            # Extract and send the generated response from OpenAI
            bot_response = response.choices[0].text.strip()  # Correct access method for new API
            await message.channel.send(bot_response)

        except Exception as e:
            # Catch any other unexpected errors and log them
            await message.channel.send("Sorry, I couldn't process that request.")
            print(f"General Error: {e}")

# Run the bot using the token from .env
client.run(TOKEN)
