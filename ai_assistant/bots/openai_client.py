import os
import openai


def call_openai(bot, message):
    """
    Send a message to OpenAI and return:
    - response text
    - actual total token usage reported by OpenAI
    """

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    openai.api_key = api_key

    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"You are the AI assistant '{bot.name}'. "
                    f"{bot.personality}"
                ),
            },
            {
                "role": "user",
                "content": message,
            },
        ],
        max_tokens=500,
    )

    response_text = response.choices[0].message["content"].strip()

    tokens_used = 0

    if response.get("usage"):
        tokens_used = response["usage"].get("total_tokens", 0)

    return response_text, tokens_used