# Standard library imports

import json
import logging
import traceback
from ai_assistant.accounts.plan_utils import (
    get_knowledge_storage_status,
)


# Django imports

from django.db.models.functions import TruncDate
from django.db.models import Count
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.views.decorators.csrf import csrf_protect
from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseNotAllowed


# Third-party imports

from rest_framework.authtoken.models import Token


# Local app imports

from ai_assistant.accounts.models import UserProfile
from ai_assistant.dashboard.models import BotUsageLog
from .models import (
    Bot,
    ChatMessage,
    Conversation,
    KnowledgeBase,
    KnowledgeChunk,
)
from .forms import BotForm, KnowledgeBaseForm
from .utils import extract_text, chunk_text
from ai_assistant.bots.chat_service import (
    ChatRateLimitError,
    ChatServiceError,
    ChatUsageLimitError,
    process_bot_message,
)
from .knowledge_utils import (
    generate_embedding_batches,
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

    plan = (
        user_profile.effective_plan
        if user_profile
        else "free"
    )

    bot_limits = {
        "free": 1,
        "premium": 5,
        "pro": 15,
    }

    bot_limit = bot_limits.get(plan, 1)

    if bot_count >= bot_limit:
        messages.error(
            request,
            f"Your {plan.capitalize()} plan allows up to {bot_limit} AI assistant"
            f"{'s' if bot_limit != 1 else ''}.",
        )
        return redirect("bots:list")

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
    """
    Return chat history for one conversation
    belonging to the authenticated user.
    """

    bot = get_object_or_404(
        Bot,
        id=bot_id,
        owner=request.user,
    )

    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    conversation_id = str(
        request.GET.get(
            "conversation_id",
            "",
        )
    ).strip()

    if conversation_id:
        conversation = get_object_or_404(
            Conversation,
            public_id=conversation_id,
            bot=bot,
            user=request.user,
        )
    else:
        conversation = (
            Conversation.objects.filter(
                bot=bot,
                user=request.user,
            )
            .order_by(
                "-updated_at",
                "-created_at",
            )
            .first()
        )

    if conversation is None:
        return JsonResponse(
            {
                "conversation_id": None,
                "messages": [],
            }
        )

    chat_messages = (
        ChatMessage.objects.filter(
            conversation=conversation,
            bot=bot,
            user=request.user,
        )
        .order_by("timestamp")
    )

    data = [
        {
            "id": message.id,
            "sender": message.sender,
            "message": message.message,
            "timestamp": (
                message.timestamp.isoformat()
            ),
        }
        for message in chat_messages
    ]

    return JsonResponse(
        {
            "conversation_id": str(
                conversation.public_id
            ),
            "title": conversation.title,
            "messages": data,
        }
    )


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
    """
    Handle web chat messages using the shared
    AI chat service.
    """

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

        user_input = str(
            data.get(
                "message",
                "",
            )
        ).strip()

        if not user_input:
            return JsonResponse(
                {
                    "error": "No message provided.",
                },
                status=400,
            )

        conversation_id = data.get(
            "conversation_id"
        )

        if conversation_id is not None:
            conversation_id = str(
                conversation_id
            ).strip()

            if not conversation_id:
                conversation_id = None

        try:
            result = process_bot_message(
                user=request.user,
                bot=bot,
                message=user_input,
                conversation=conversation_id,
            )

        except ChatUsageLimitError as error:
            usage_status = error.usage_status

            response_data = {
                "error": str(error),
                "plan": usage_status["plan"],
            }

            if usage_status[
                "monthly_message_limit_reached"
            ]:
                response_data.update(
                    {
                        "monthly_messages_used": (
                            usage_status[
                                "monthly_messages_used"
                            ]
                        ),
                        "monthly_limit": (
                            usage_status[
                                "monthly_message_limit"
                            ]
                        ),
                    }
                )

            return JsonResponse(
                response_data,
                status=403,
            )

        except ChatRateLimitError as error:
            return JsonResponse(
                {
                    "error": str(error),
                    "retry_after_seconds": (
                        error.retry_after_seconds
                    ),
                },
                status=429,
            )

        except ChatServiceError as error:
            logger.error(
                "Chat service error: %s",
                error,
            )

            return JsonResponse(
                {
                    "error": str(error),
                },
                status=400,
            )

        except Exception:
            logger.error(
                "AI processing failed:\n%s",
                traceback.format_exc(),
            )

            return JsonResponse(
                {
                    "error": "AI processing failed.",
                },
                status=500,
            )

        return JsonResponse(
            {
                "reply": result["response"],
                "conversation_id": result[
                    "conversation_id"
                ],
                "plan": result["plan"],
                "monthly_messages_used": (
                    result[
                        "monthly_messages_used"
                    ]
                ),
                "monthly_limit": (
                    result["monthly_limit"]
                ),
                "in_domain": (
                    result["in_domain"]
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

    messages_over_time = (
        ChatMessage.objects.filter(
            user=request.user
        )
        .annotate(
            day=TruncDate("timestamp")
        )
        .values("day")
        .annotate(
            count=Count("id")
        )
        .order_by("day")
    )

    time_data = {
        "labels": [],
        "counts": [],
    }

    for item in messages_over_time:
        time_data["labels"].append(
            item["day"].isoformat()
        )
        time_data["counts"].append(
            item["count"]
        )

    return render(
        request,
        "bots/analytics_dashboard.html",
        {
            "bot_data": json.dumps(
                bot_data
            ),
            "time_data": json.dumps(
                time_data
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
def delete_knowledge(request, bot_id, knowledge_id):
    bot = get_object_or_404(
        Bot,
        id=bot_id,
        owner=request.user,
    )

    knowledge = get_object_or_404(
        KnowledgeBase,
        id=knowledge_id,
        bot=bot,
    )

    if request.method == "POST":
        if knowledge.file:
            try:
                knowledge.file.delete(save=False)
            except Exception:
                logger.exception(
                    "Failed to delete knowledge file %s",
                    knowledge.file.name,
                )

        knowledge.delete()

        messages.success(
            request,
            "Knowledge deleted successfully.",
        )

    return redirect(
        "bots:playground",
        bot_id=bot.id,
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

    knowledge_files = KnowledgeBase.objects.filter(
    bot=bot,
    ).order_by("-id")

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

            if file:
                source_size_bytes = file.size
            else:
                source_size_bytes = len(
                    manual_text.encode("utf-8")
                )

            storage_status = get_knowledge_storage_status(
                request.user,
                incoming_size_bytes=source_size_bytes,
            )

            if not storage_status["allowed"]:
                used_mb = (
                    storage_status["storage_used_bytes"]
                    / (1024 * 1024)
                )
                limit_mb = (
                    storage_status["storage_limit_bytes"]
                    / (1024 * 1024)
                )

                messages.error(
                    request,
                    (
                        "Knowledge storage limit reached. "
                        f"You are using {used_mb:.1f} MB of "
                        f"{limit_mb:.0f} MB available on your "
                        f"{storage_status['plan'].capitalize()} plan."
                    ),
                )

                return redirect(
                    "bots:playground",
                    bot_id=bot.id,
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

                if not chunks:
                    raise ValueError("No valid knowledge chunks were generated.")

                def record_embedding_usage(usage):
                    if usage["tokens_used"] > 0:
                        BotUsageLog.objects.create(
                            user=request.user, bot=bot, **usage,
                        )

                embeddings = generate_embedding_batches(
                    chunks, record_usage=record_embedding_usage,
                )
                prepared_chunks = list(zip(chunks, embeddings))

                # Keep API calls outside the knowledge database transaction.
                # Usage logs remain recorded even if a later upload step fails.
                kb = KnowledgeBase(
                    bot=bot,
                    file=file if file else None,
                    uploaded_by=request.user,
                    source_size_bytes=source_size_bytes,
                )
                try:
                    if file:
                        file.seek(0)
                    with transaction.atomic():
                        kb.save()
                        for chunk, embedding in prepared_chunks:
                            KnowledgeChunk.objects.create(
                                knowledge_file=kb,
                                text=chunk,
                                embedding=embedding,
                            )
                except Exception:
                    # File storage does not participate in database rollback.
                    if kb.file and kb.file._committed:
                        try:
                            kb.file.delete(save=False)
                        except Exception:
                            logger.exception(
                                "Failed to clean up knowledge upload file %s",
                                kb.file.name,
                            )
                    raise

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
                logger.error("Knowledge upload failed (%s).", error,)

                messages.error(
                    request,
                    (
                        "Failed to process file. Please check the content and try again."
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
            "knowledge_files": knowledge_files,
        },
    )


@login_required
def discord_setup(request, bot_id):
    bot = get_object_or_404(
        Bot,
        id=bot_id,
        owner=request.user,
    )

    if request.user.profile.effective_plan != "pro":
        messages.warning(
            request,
            "Discord integration is available on the Pro plan."
        )
        return redirect("payments:billing")

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
