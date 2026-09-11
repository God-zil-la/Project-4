from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import IntegrityError
from django.test import RequestFactory, TestCase

from ai_assistant.accounts.models import (
    UserProfile,
    current_month_start,
)
from ai_assistant.bots.chat_service import (
    _save_chat_exchange,
    process_bot_message,
)
from ai_assistant.bots.forms import KnowledgeBaseForm
from ai_assistant.bots.models import (
    Bot,
    ChatMessage,
    Conversation,
    KnowledgeBase,
)
from ai_assistant.bots.views import bot_chat_playground


class LocalCompletionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="local-check"
        )

        self.bot = Bot.objects.create(
            owner=self.user,
            name="Local",
        )

    def test_manual_only_form_and_empty_input(self):
        self.assertTrue(
            KnowledgeBaseForm(
                data={
                    "manual_text": "Useful knowledge."
                }
            ).is_valid()
        )

        self.assertFalse(
            KnowledgeBaseForm(
                data={
                    "manual_text": "  "
                }
            ).is_valid()
        )

    def test_manual_only_upload_persists_without_file(self):
        request = RequestFactory().post(
            "/",
            {
                "manual_text": "Useful knowledge."
            },
        )

        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        request._dont_enforce_csrf_checks = True

        with patch(
            "ai_assistant.bots.views.generate_embedding_batches",
            return_value=[[1.0]],
        ) as batches:
            response = bot_chat_playground(
                request,
                self.bot.pk,
            )

        self.assertEqual(
            response.status_code,
            302,
        )

        kb = KnowledgeBase.objects.get()

        self.assertFalse(kb.file)

        self.assertEqual(
            kb.chunks.get().text,
            "Useful knowledge.",
        )

        batches.assert_called_once()

    def test_stale_instances_do_not_lose_reservations(self):
        first = UserProfile.objects.get(
            user=self.user
        )

        second = UserProfile.objects.get(
            user=self.user
        )

        first_reservation = first.reserve_message_slot(
            150
        )

        second_reservation = second.reserve_message_slot(
            150
        )

        self.assertIsNotNone(
            first_reservation
        )

        self.assertIsNotNone(
            second_reservation
        )

        first.refresh_from_db()

        self.assertEqual(
            first.monthly_message_count,
            2,
        )

    def test_stale_reset_does_not_erase_new_month_usage(self):
        month_start = current_month_start()

        previous_month_start = (
            month_start - timedelta(days=1)
        ).replace(day=1)

        UserProfile.objects.filter(
            user=self.user
        ).update(
            message_count_period_start=previous_month_start,
            monthly_message_count=10,
        )

        stale = UserProfile.objects.get(
            user=self.user
        )

        reservation = (
            self.user.profile.reserve_message_slot(
                150
            )
        )

        self.assertIsNotNone(
            reservation
        )

        stale.reset_monthly_count()

        self.assertEqual(
            stale.monthly_message_count,
            1,
        )

        self.assertEqual(
            stale.message_count_period_start,
            month_start,
        )

    def test_partial_exchange_rolls_back(self):
        conversation = Conversation.objects.create(
            user=self.user,
            bot=self.bot,
        )

        create = ChatMessage.objects.create

        def fail_assistant(**kwargs):
            if (
                kwargs["sender"]
                == ChatMessage.SENDER_ASSISTANT
            ):
                raise IntegrityError(
                    "Simulated failure"
                )

            return create(**kwargs)

        with patch(
            "ai_assistant.bots.chat_service."
            "ChatMessage.objects.create",
            side_effect=fail_assistant,
        ):
            with self.assertRaises(
                IntegrityError
            ):
                _save_chat_exchange(
                    conversation,
                    self.bot,
                    self.user,
                    "Question",
                    "Answer",
                )

        self.assertEqual(
            ChatMessage.objects.count(),
            0,
        )

        self.user.profile.refresh_from_db()

        self.assertEqual(
            self.user.profile.monthly_message_count,
            0,
        )

    def test_failed_exchange_releases_reserved_quota(self):
        self.user.profile.monthly_message_count = 0
        self.user.profile.save(
            update_fields=[
                "monthly_message_count",
            ]
        )

        domain_result = {
            "in_domain": False,
            "tokens_used": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "model": "gpt-4o-mini",
        }

        with patch(
            "ai_assistant.bots.chat_service."
            "check_message_domain",
            return_value=domain_result,
        ):
            with patch(
                "ai_assistant.bots.chat_service."
                "_save_chat_exchange",
                side_effect=IntegrityError(
                    "Exchange failure"
                ),
            ):
                with self.assertRaises(
                    IntegrityError
                ):
                    process_bot_message(
                        user=self.user,
                        bot=self.bot,
                        message="Question",
                    )

        self.user.profile.refresh_from_db()

        self.assertEqual(
            self.user.profile.monthly_message_count,
            0,
        )

        self.assertEqual(
            ChatMessage.objects.count(),
            0,
        )

    def test_non_object_and_non_text_public_chat_input(self):
        import json

        profile = self.user.profile

        profile.plan = UserProfile.PLAN_PRO
        profile.save(
            update_fields=["plan"]
        )

        profile.generate_api_key()

        for payload in [
            [],
            "text",
            {
                "message": None
            },
            {
                "message": {
                    "nested": "text"
                }
            },
        ]:
            response = self.client.post(
                "/accounts/api/public-chat/",
                json.dumps(payload),
                content_type="application/json",
                HTTP_X_API_KEY=profile.api_key,
                secure=True,
            )

            self.assertEqual(
                response.status_code,
                400,
            )

    def test_malformed_authenticated_api_input_has_no_side_effects(
        self
    ):
        import json

        from django.core.cache import cache

        cache.clear()

        self.client.force_login(
            self.user
        )

        conversation = Conversation.objects.create(
            user=self.user,
            bot=self.bot,
            title="Original",
        )

        cases = [
            (
                "/bots/api/conversations/",
                "post",
                [],
            ),
            (
                "/bots/api/conversations/",
                "post",
                {
                    "bot_id": self.bot.pk,
                    "title": None,
                },
            ),
            (
                (
                    "/bots/api/conversations/"
                    f"{conversation.public_id}/"
                ),
                "patch",
                {
                    "title": {}
                },
            ),
            (
                (
                    "/bots/api/bot/"
                    f"{self.bot.pk}/chat/"
                ),
                "post",
                [],
            ),
            (
                (
                    "/bots/api/bot/"
                    f"{self.bot.pk}/chat/"
                ),
                "post",
                {
                    "message": None
                },
            ),
            (
                (
                    "/bots/api/bot/"
                    f"{self.bot.pk}/chat/"
                ),
                "post",
                {
                    "message": "Hello",
                    "conversation_id": {},
                },
            ),
        ]

        with patch(
            "ai_assistant.bots.api_views."
            "process_bot_message"
        ) as process:
            for url, method, payload in cases:
                response = getattr(
                    self.client,
                    method,
                )(
                    url,
                    json.dumps(payload),
                    content_type="application/json",
                    secure=True,
                )

                self.assertEqual(
                    response.status_code,
                    400,
                )

            process.assert_not_called()

        conversation.refresh_from_db()

        self.assertEqual(
            conversation.title,
            "Original",
        )

        self.assertEqual(
            Conversation.objects.count(),
            1,
        )

        self.assertEqual(
            ChatMessage.objects.count(),
            0,
        )

        self.user.profile.refresh_from_db()

        self.assertEqual(
            self.user.profile.monthly_message_count,
            0,
        )