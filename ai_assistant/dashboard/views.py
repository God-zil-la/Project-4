import os
import openai
from django.shortcuts import render
from dotenv import load_dotenv

load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")


def home(request):
    """
    Render the homepage and handle user chat input to GPT.

    If the request is POST and includes a message, sends it to OpenAI's ChatCompletion API
    and returns the assistant's reply. Otherwise, shows the homepage with no response.
    """
    bot_response = None

    if request.method == "POST":
        user_message = request.POST.get("message", "").strip()

        if user_message:
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": user_message},
                    ]
                )
                bot_response = response['choices'][0]['message']['content'].strip()
            except Exception as e:
                bot_response = f"⚠️ Error: {str(e)}"
        else:
            bot_response = "⚠️ Message cannot be empty."

    return render(request, 'dashboard/index.html', {
        'bot_response': bot_response
    })
