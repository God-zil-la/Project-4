# Standard library imports

import os
import json
import logging
import traceback


# Django imports

from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseNotAllowed


# Third-party imports

import openai
from rest_framework.authtoken.models import Token


# Local app imports

from ai_assistant.accounts.models import UserProfile
from ai_assistant.accounts.plan_utils import get_ai_usage_status
from ai_assistant.dashboard.models import BotUsageLog
from .models import Bot, ChatMessage, KnowledgeBase, KnowledgeChunk
from .forms import BotForm, KnowledgeBaseForm
from .utils import extract_text, chunk_text
from .knowledge_utils import (
    generate_embedding,
    search_relevant_chunks,
    render_system_message,
    check_message_domain,
)


# Setup

logger = logging.getLogger(__name__)


@login_required
def bot_list(request):
    logger.info("bot_list view called")

    bots = Bot.objects.filter(owner=request.user)

    return render(
        request,
        "bots/bot_list.html",
        {"bots": bots},
    )


@login_required
def my_bots(request):
    user_bots = Bot.objects.filter(owner=request.user)

    return render(
        request,
        "bots/my_bots.html",
        {"bots": user_bots},
    )


@login_required
def create_bot(request):
    try:
        user_profile = request.user.profile
    except UserProfile.DoesNotExist:
        user_profile = None

    bot_count = Bot.objects.filter(owner=request.user).count()

    if (
        not user_profile or not user_profile.is_subscribed
    ) and bot_count >= 3:
        messages.error(
            request,
            "Free plan allows up to 3 bots. Upgrade to Premium for more.",
        )
        return redirect("bots:my-bots")

    if request.method == "POST":
        form = BotForm(request.POST)

        if form.is_valid():
            duplicate_exists = Bot.objects.filter(
                owner=request.user,
                name=form.cleaned_data["name"],
            ).exists()

            if duplicate_exists:
                messages.error(
                    request,
                    (
                        "You already have a bot with this name. "
                        "Please choose a different name."
                    ),
                )

                return render(
                    request,
                    "bots/create_bot.html",
                    {"form": form},
                )

            bot = form.save(commit=False)
            bot.owner = request.user
            bot.save()

            messages.success(
                request,
                "Bot created successfully!",
            )

            return redirect("bots:my-bots")

        messages.error(
            request,
            "Please correct the errors below.",
        )

    else:
        form = BotForm()

    return render(
        request,
        "bots/create_bot.html",
        {"form": form},
    )


@login_required
def bot_chat_api(request, bot_id):
    bot = get_object_or_404(
        Bot,
        id=bot_id,
        owner=request.user,
    )

    if request.method == "GET":
        chat_messages = ChatMessage.objects.filter(
            bot=bot,
            user=request.user,
        ).order_by("timestamp")

        data = [
            {
                "sender": message.sender,
                "message": message.message,
            }
            for message in chat_messages
        ]

        return JsonResponse(
            {"messages": data}
        )

    return HttpResponseNotAllowed(["GET"])


@login_required
def edit_bot(request, bot_id):
    bot = get_object_or_404(
        Bot,
        id=bot_id,
        owner=request.user,
    )

    if request.method == "POST":
        form = BotForm(
            request.POST,
            instance=bot,
        )

        if form.is_valid():
            edited_bot = form.save(commit=False)
            edited_bot.owner = request.user
            edited_bot.save()

            messages.success(
                request,
                "Bot updated successfully!",
            )

            return redirect("bots:list")

        messages.error(
            request,
            "Please fix the errors below.",
        )

    else:
        form = BotForm(instance=bot)

    return render(
        request,
        "bots/edit_bot.html",
        {
            "form": form,
        },
    )


@login_required
def delete_bot(request, bot_id):
    bot = get_object_or_404(
        Bot,
        id=bot_id,
        owner=request.user,
    )

    if request.method == "POST":
        bot.delete()
        return redirect("bots:list")

    return render(
        request,
        "bots/confirm_delete.html",
        {
            "bot": bot,
        },
    )


@login_required
@csrf_protect
def ajax_chat(request, bot_id):
    if request.method != "POST":
        return JsonResponse(
            {
                "error": "Invalid request method.",
            },
            status=405,
        )

    try:
        bot = get_object_or_404(
            Bot,
            id=bot_id,
            owner=request.user,
        )

        try:
            data = json.loads(
                request.body.decode("utf-8")
            )
        except json.JSONDecodeError:
            return JsonResponse(
                {
                    "error": "Invalid JSON data.",
                },
                status=400,
            )

        user_input = data.get(
            "message",
            "",
        ).strip()

        if not user_input:
            return JsonResponse(
                {
                    "error": "No message provided.",
                },
                status=400,
            )

        # -------------------------------------------------
        # AI PLAN USAGE CONTROL
        # -------------------------------------------------
        user_profile = getattr(
            request.user,
            "profile",
            None,
        )

        if not user_profile:
            return JsonResponse(
                {
                    "error": "User profile not found.",
                },
                status=500,
            )

        usage_status = get_ai_usage_status(
            request.user
        )

        if not usage_status["allowed"]:
            if usage_status[
                "daily_limit_reached"
            ]:
                return JsonResponse(
                    {
                        "error": (
                            "Daily AI message limit "
                            "reached"
                        ),
                        "plan": usage_status["plan"],
                        "daily_messages_used": (
                            usage_status[
                                "daily_messages_used"
                            ]
                        ),
                        "daily_limit": (
                            usage_status[
                                "daily_message_limit"
                            ]
                        ),
                    },
                    status=403,
                )

            if usage_status[
                "monthly_cost_limit_reached"
            ]:
                return JsonResponse(
                    {
                        "error": (
                            "Monthly AI usage limit "
                            "reached"
                        ),
                        "plan": usage_status["plan"],
                    },
                    status=403,
                )

            return JsonResponse(
                {
                    "error": "AI usage is unavailable.",
                },
                status=403,
            )

        # -------------------------------------------------
        # CATEGORY DOMAIN CHECK
        # -------------------------------------------------
        domain_check = check_message_domain(
            bot,
            user_input,
        )

        if domain_check["tokens_used"] > 0:
            BotUsageLog.objects.create(
                user=request.user,
                bot=bot,
                tokens_used=domain_check[
                    "tokens_used"
                ],
                input_tokens=domain_check[
                    "input_tokens"
                ],
                output_tokens=domain_check[
                    "output_tokens"
                ],
                model=domain_check[
                    "model"
                ],
            )

        if not domain_check["in_domain"]:
            reply = (
                f"I specialize in "
                f"{bot.get_category_display()}. "
                f"Please ask me something related "
                f"to that category."
            )

            ChatMessage.objects.create(
                bot=bot,
                user=request.user,
                sender="user",
                message=user_input,
            )

            ChatMessage.objects.create(
                bot=bot,
                user=request.user,
                sender="assistant",
                message=reply,
            )

            user_profile.increment_message_count()

            return JsonResponse(
                {
                    "reply": reply,
                    "plan": user_profile.plan,
                    "daily_messages_used": (
                        user_profile.daily_message_count
                    ),
                    "daily_limit": (
                        usage_status[
                            "daily_message_limit"
                        ]
                    ),
                }
            )

        # -------------------------------------------------
        # SAVE USER MESSAGE
        # -------------------------------------------------
        ChatMessage.objects.create(
            bot=bot,
            user=request.user,
            sender="user",
            message=user_input,
        )

        # -------------------------------------------------
        # COST CONTROL
        #
        # Only send the latest 20 messages to OpenAI.
        # -------------------------------------------------
        latest_messages = list(
            ChatMessage.objects.filter(
                bot=bot,
                user=request.user,
            )
            .order_by("-timestamp")[:20]
        )

        latest_messages.reverse()

               # -------------------------------------------------
        # KNOWLEDGE BASE
        # -------------------------------------------------
        try:
            knowledge_result = search_relevant_chunks(
                bot,
                user_input,
                include_usage=True,
            )

            relevant_chunks = knowledge_result[
                "chunks"
            ]

            if knowledge_result["tokens_used"] > 0:
                BotUsageLog.objects.create(
                    user=request.user,
                    bot=bot,
                    tokens_used=knowledge_result[
                        "tokens_used"
                    ],
                    input_tokens=knowledge_result[
                        "input_tokens"
                    ],
                    output_tokens=knowledge_result[
                        "output_tokens"
                    ],
                    model=knowledge_result["model"],
                )

            knowledge_text = (
                "\n\n".join(relevant_chunks)
                if relevant_chunks
                else ""
            )

            system_message = render_system_message(
                bot,
                knowledge_text,
            )

        except Exception:
            logger.error(
                "Knowledge search/render failed:\n%s",
                traceback.format_exc(),
            )

            knowledge_text = ""

            system_message = render_system_message(
                bot,
                "",
            )


        # -------------------------------------------------
        # BUILD OPENAI CHAT HISTORY
        # -------------------------------------------------
        history = [
            {
                "role": "system",
                "content": system_message,
            }
        ]

        for chat_message in latest_messages:
            history.append(
                {
                    "role": (
                        "user"
                        if chat_message.sender == "user"
                        else "assistant"
                    ),
                    "content": chat_message.message,
                }
            )

        # -------------------------------------------------
        # OPENAI
        # -------------------------------------------------
        openai.api_key = os.getenv(
            "OPENAI_API_KEY"
        )

        if not openai.api_key:
            logger.error(
                "OPENAI_API_KEY is missing."
            )

            return JsonResponse(
                {
                    "error": (
                        "AI service is not configured."
                    ),
                },
                status=500,
            )

        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=history,
        )

        reply = (
            response
            .choices[0]
            .message["content"]
            .strip()
        )

        # -------------------------------------------------
        # TOKEN LOGGING
        # -------------------------------------------------
        try:
            usage = response["usage"]

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
                "gpt-4o-mini",
            )

            BotUsageLog.objects.create(
                user=request.user,
                bot=bot,
                tokens_used=tokens_used,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=model_name,
            )

            logger.info(
                (
                    "AI usage - user=%s bot=%s "
                    "input=%s output=%s total=%s "
                    "model=%s"
                ),
                request.user.id,
                bot.id,
                input_tokens,
                output_tokens,
                tokens_used,
                model_name,
            )

        except Exception:
            logger.warning(
                "Could not save BotUsageLog:\n%s",
                traceback.format_exc(),
            )

        # -------------------------------------------------
        # SAVE ASSISTANT MESSAGE
        # -------------------------------------------------
        ChatMessage.objects.create(
            bot=bot,
            user=request.user,
            sender="assistant",
            message=reply,
        )

        # Count only successful AI requests.
        user_profile.increment_message_count()

        return JsonResponse(
            {
                "reply": reply,
                "plan": user_profile.plan,
                "daily_messages_used": (
                    user_profile.daily_message_count
                ),
                "daily_limit": (
                    usage_status[
                        "daily_message_limit"
                    ]
                ),
            }
        )

    except Exception:
        logger.error(
            "ajax_chat error:\n%s",
            traceback.format_exc(),
        )

        return JsonResponse(
            {
                "error": "An error occurred.",
            },
            status=500,
        )


@login_required
def analytics_dashboard(request):
    bots = Bot.objects.filter(
        owner=request.user
    )

    bot_data = {
        "labels": [],
        "counts": [],
    }

    for bot in bots:
        bot_data["labels"].append(
            bot.name
        )

        bot_data["counts"].append(
            ChatMessage.objects.filter(
                bot=bot,
                user=request.user,
            ).count()
        )

    user_data = {
        "labels": [
            request.user.username
        ],
        "counts": [
            ChatMessage.objects.filter(
                user=request.user
            ).count()
        ],
    }

    return render(
        request,
        "bots/analytics_dashboard.html",
        {
            "bot_data": json.dumps(
                bot_data
            ),
            "user_data": json.dumps(
                user_data
            ),
        },
    )


@staff_member_required
def admin_dashboard(request):
    bots = Bot.objects.all()
    users = User.objects.all()

    bot_data = {
        "labels": [],
        "counts": [],
    }

    for bot in bots:
        bot_data["labels"].append(
            bot.name
        )

        bot_data["counts"].append(
            ChatMessage.objects.filter(
                bot=bot
            ).count()
        )

    user_data = {
        "labels": [],
        "counts": [],
    }

    for user in users:
        user_data["labels"].append(
            user.username
        )

        user_data["counts"].append(
            ChatMessage.objects.filter(
                user=user
            ).count()
        )

    return render(
        request,
        "bots/analytics_dashboard.html",
        {
            "bot_data": json.dumps(
                bot_data
            ),
            "user_data": json.dumps(
                user_data
            ),
        },
    )


@login_required
@csrf_protect
def bot_chat_playground(request, bot_id):
    bot = get_object_or_404(
        Bot,
        id=bot_id,
        owner=request.user,
    )

    chat_messages = ChatMessage.objects.filter(
        bot=bot,
        user=request.user,
    ).order_by("timestamp")

    if request.method == "POST":
        knowledge_form = KnowledgeBaseForm(
            request.POST,
            request.FILES,
        )

        if knowledge_form.is_valid():
            file = request.FILES.get(
                "file"
            )

            manual_text = (
                knowledge_form.cleaned_data.get(
                    "manual_text"
                )
            )

            source_text = ""
            filename = ""

            try:
                if file:
                    filename = file.name

                    file.seek(0)

                    source_text = extract_text(
                        file,
                        filename,
                    )

                elif manual_text:
                    filename = (
                        "manual_input.txt"
                    )

                    source_text = manual_text

                if not source_text.strip():
                    messages.error(
                        request,
                        (
                            "No valid content "
                            "extracted from input."
                        ),
                    )

                    return redirect(
                        "bots:playground",
                        bot_id=bot.id,
                    )

                chunks = chunk_text(
                    source_text
                )

                kb = KnowledgeBase.objects.create(
                    bot=bot,
                    file=(
                        file
                        if file
                        else None
                    ),
                    uploaded_by=request.user,
                )

                for chunk in chunks:
                    embedding_result = generate_embedding(
                        chunk,
                        include_usage=True,
                    )

                    embedding = embedding_result[
                        "embedding"
                    ]

                    if embedding:
                        KnowledgeChunk.objects.create(
                            knowledge_file=kb,
                            text=chunk,
                            embedding=embedding,
                        )

                    if embedding_result["tokens_used"] > 0:
                        BotUsageLog.objects.create(
                            user=request.user,
                            bot=bot,
                            tokens_used=embedding_result[
                                "tokens_used"
                            ],
                            input_tokens=embedding_result[
                                "input_tokens"
                            ],
                            output_tokens=embedding_result[
                                "output_tokens"
                            ],
                            model=embedding_result["model"],
                        )

                messages.success(
                    request,
                    (
                        "Knowledge uploaded and "
                        "processed successfully!"
                    ),
                )

                return redirect(
                    "bots:playground",
                    bot_id=bot.id,
                )

            except Exception as error:
                logger.error(
                    "Knowledge upload error: %s",
                    str(error),
                )

                messages.error(
                    request,
                    (
                        "Failed to process file: "
                        f"{str(error)}"
                    ),
                )

        else:
            messages.error(
                request,
                (
                    "Invalid submission. "
                    "Please upload a file or "
                    "paste some text."
                ),
            )

    else:
        knowledge_form = (
            KnowledgeBaseForm()
        )

    return render(
        request,
        "bots/playground.html",
        {
            "bot": bot,
            "chat_messages": chat_messages,
            "knowledge_form": knowledge_form,
        },
    )


@login_required
def discord_setup(request, bot_id):
    bot = get_object_or_404(
        Bot,
        id=bot_id,
        owner=request.user,
    )

    token, _ = Token.objects.get_or_create(
        user=request.user
    )

    return render(
        request,
        "bots/discord/setup.html",
        {
            "bot": bot,
            "api_token": token.key,
        },
    )