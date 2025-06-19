import os
import openai
from django.shortcuts import render
from dotenv import load_dotenv

load_dotenv()  # Load .env variables

openai.api_key = os.getenv("OPENAI_API_KEY")

def home(request):
    bot_response = None

    if request.method == "POST":
        user_message = request.POST.get("message")

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": user_message},
                ]
            )
            bot_response = response.choices[0].message["content"]
        except Exception as e:
            bot_response = f"Error: {str(e)}"

    return render(request, 'dashboard/index.html', {
        'bot_response': bot_response
    })
