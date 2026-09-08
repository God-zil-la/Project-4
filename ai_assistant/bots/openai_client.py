import os

import openai


def call_openai(bot, message):
    """
    Send a message to OpenAI and return:
    - response text
    - total token usage
    - input token usage
    - output token usage
    - actual model name
    """
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing")

    openai.api_key = api_key

    requested_model = "gpt-4o-mini"

    response = openai.ChatCompletion.create(
        model=requested_model,
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

    response_text = (
        response
        .choices[0]
        .message["content"]
        .strip()
    )

    usage = response.get("usage", {})

    input_tokens = usage.get(
        "prompt_tokens",
        0,
    )

    output_tokens = usage.get(
        "completion_tokens",
        0,
    )

    tokens_used = usage.get(
        "total_tokens",
        0,
    )

    model_name = response.get(
        "model",
        requested_model,
    )

    return (
        response_text,
        tokens_used,
        input_tokens,
        output_tokens,
        model_name,
    )