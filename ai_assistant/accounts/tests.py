from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from ai_assistant.bots.models import Bot, KnowledgeBase, KnowledgeChunk
from ai_assistant.bots.views import bot_chat_playground
from ai_assistant.dashboard.models import BotUsageLog


class AnalyticsDashboardTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="analytics-owner")
        self.client.force_login(self.user)

    def test_navigation_for_regular_and_staff_users(self):
        for is_staff in [False, True]:
            self.user.is_staff = is_staff
            self.user.save()

            for path in ["/", "/bots/", "/payments/"]:
                response = self.client.get(path)
                self.assertContains(
                    response,
                    'href="/bots/analytics/"',
                )

    def test_anonymous_access_requires_login_and_hides_link(self):
        self.client.logout()

        self.assertNotContains(
            self.client.get("/"),
            'href="/bots/analytics/"',
        )

        response = self.client.get("/bots/analytics/")

        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "/accounts/login/",
            response["Location"],
        )

    def test_existing_dashboard_template_and_empty_charts(self):
        import json

        response = self.client.get("/bots/analytics/")

        self.assertTemplateUsed(
            response,
            "bots/analytics_dashboard.html",
        )

        self.assertContains(
            response,
            'id="botUsageChart"',
        )

        self.assertContains(
            response,
            'id="timeUsageChart"',
        )

        self.assertEqual(
            json.loads(response.context["bot_data"]),
            {
                "labels": [],
                "counts": [],
            },
        )

        self.assertEqual(
            json.loads(response.context["time_data"]),
            {
                "labels": [],
                "counts": [],
            },
        )

    def test_chart_data_is_scoped_to_current_user(self):
        import json
        from ai_assistant.bots.models import ChatMessage

        other = User.objects.create_user(
            username="other-analytics-owner"
        )

        own_bot = Bot.objects.create(
            owner=self.user,
            name="My bot",
        )

        other_bot = Bot.objects.create(
            owner=other,
            name="Other bot",
        )

        own_message = ChatMessage.objects.create(
            bot=own_bot,
            user=self.user,
            message="Hello",
            sender="user",
        )

        ChatMessage.objects.create(
            bot=own_bot,
            user=other,
            message="Private",
            sender="user",
        )

        ChatMessage.objects.create(
            bot=other_bot,
            user=other,
            message="Private",
            sender="user",
        )

        response = self.client.get("/bots/analytics/")

        self.assertEqual(
            json.loads(response.context["bot_data"]),
            {
                "labels": ["My bot"],
                "counts": [1],
            },
        )

        expected_day = own_message.timestamp.date().isoformat()

        self.assertEqual(
            json.loads(response.context["time_data"]),
            {
                "labels": [expected_day],
                "counts": [1],
            },
        )


class KnowledgeUploadTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)

        self.settings_override = self.settings(
            MEDIA_ROOT=self.media.name
        )
        self.settings_override.enable()
        self.addCleanup(
            self.settings_override.disable
        )

        self.user = User.objects.create_user(
            username="upload-owner"
        )

        self.bot = Bot.objects.create(
            owner=self.user,
            name="Upload bot",
        )

        self.existing = KnowledgeBase.objects.create(
            bot=self.bot,
            uploaded_by=self.user,
        )

        KnowledgeChunk.objects.create(
            knowledge_file=self.existing,
            text="Existing knowledge",
            embedding=[1.0],
        )

        self.result = dict(
            embedding=[0.5],
            tokens_used=3,
            input_tokens=3,
            output_tokens=0,
            model="text-embedding-3-small",
        )

    def upload(self, results=None):
        request = RequestFactory().post(
            "/",
            {
                "file": SimpleUploadedFile(
                    "knowledge.txt",
                    b"First. Second.",
                )
            },
        )

        request.user = self.user
        request._dont_enforce_csrf_checks = True
        request.session = {}
        request._messages = FallbackStorage(request)

        def response_batches(*args, **kwargs):
            vectors = []

            for result in results or [
                self.result,
                self.result,
            ]:
                if isinstance(result, Exception):
                    raise result

                kwargs["record_usage"](
                    {
                        key: value
                        for key, value in result.items()
                        if key != "embedding"
                    }
                )

                if not result["embedding"]:
                    raise ValueError("Empty embedding")

                vectors.append(
                    result["embedding"]
                )

            return vectors

        with patch(
            "ai_assistant.bots.views.chunk_text",
            return_value=["First.", "Second."],
        ), patch(
            "ai_assistant.bots.views.generate_embedding_batches",
            side_effect=response_batches,
        ), patch(
            "ai_assistant.bots.views.render",
            return_value=HttpResponse(),
        ):
            response = bot_chat_playground(
                request,
                self.bot.pk,
            )

        self.assertIn(
            response.status_code,
            (200, 302),
        )

        return response, [
            str(message)
            for message in request._messages
        ]

    def assert_no_partial_upload(self):
        self.assertEqual(
            KnowledgeBase.objects.count(),
            1,
        )

        self.assertEqual(
            KnowledgeChunk.objects.count(),
            1,
        )

        self.assertEqual(
            self.existing.chunks.get().text,
            "Existing knowledge",
        )

        self.assertFalse(
            any(
                path.is_file()
                for path in Path(
                    self.media.name
                ).rglob("*")
            )
        )

    def test_success_saves_all_chunks_file_and_usage(self):
        response, messages = self.upload()

        self.assertEqual(
            response.status_code,
            302,
        )

        kb = KnowledgeBase.objects.exclude(
            pk=self.existing.pk
        ).get()

        self.assertEqual(
            list(
                kb.chunks.values_list(
                    "text",
                    flat=True,
                )
            ),
            ["First.", "Second."],
        )

        with kb.file.open("rb") as uploaded:
            self.assertEqual(
                uploaded.read(),
                b"First. Second.",
            )

        self.assertEqual(
            BotUsageLog.objects.count(),
            2,
        )

        self.assertIn(
            "Knowledge uploaded and processed successfully!",
            messages,
        )

    def test_later_embedding_failure_leaves_existing_knowledge(self):
        _, messages = self.upload(
            [
                self.result,
                RuntimeError(
                    "Embedding failed"
                ),
            ]
        )

        self.assert_no_partial_upload()

        self.assertEqual(
            BotUsageLog.objects.count(),
            1,
        )

        self.assertTrue(
            any(
                "Failed to process file"
                in message
                for message in messages
            )
        )

    def test_empty_embedding_is_failure(self):
        self.upload(
            [
                self.result,
                dict(
                    self.result,
                    embedding=[],
                ),
            ]
        )

        self.assert_no_partial_upload()

    def test_later_chunk_failure_rolls_back_parent_and_file(self):
        create = KnowledgeChunk.objects.create
        calls = []

        def fail_second(**kwargs):
            calls.append(kwargs)

            if len(calls) == 2:
                raise IntegrityError(
                    "Chunk insert failed"
                )

            return create(**kwargs)

        with patch(
            "ai_assistant.bots.views.KnowledgeChunk.objects.create",
            side_effect=fail_second,
        ):
            self.upload()

        self.assertEqual(
            len(calls),
            2,
        )

        self.assert_no_partial_upload()

        self.assertEqual(
            BotUsageLog.objects.count(),
            2,
        )

    def test_parent_insert_failure_cleans_saved_file(self):
        with patch.object(
            KnowledgeBase,
            "save_base",
            side_effect=IntegrityError(
                "Parent insert failed"
            ),
        ):
            self.upload()

        self.assert_no_partial_upload()

    def test_storage_failure_leaves_no_knowledge(self):
        storage = KnowledgeBase._meta.get_field(
            "file"
        ).storage

        with patch.object(
            storage,
            "save",
            side_effect=OSError(
                "Storage unavailable"
            ),
        ):
            self.upload()

        self.assert_no_partial_upload()


class EmbeddingBatchTests(TestCase):
    def response(self, count, tokens=7):
        return {
            "data": [
                {
                    "index": i,
                    "embedding": [
                        float(i),
                        1.0,
                    ],
                }
                for i in reversed(
                    range(count)
                )
            ],
            "usage": {
                "prompt_tokens": tokens,
                "total_tokens": tokens,
            },
            "model": "text-embedding-3-small",
        }

    @patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "test-only"},
    )
    def test_order_and_usage_across_batches(self):
        from ai_assistant.bots.knowledge_utils import (
            generate_embedding_batches,
        )

        usage = []

        with patch(
            "ai_assistant.bots.knowledge_utils.openai.Embedding.create",
            side_effect=[
                self.response(32),
                self.response(1, 2),
            ],
        ) as api:
            result = generate_embedding_batches(
                ["text"] * 33,
                usage.append,
            )

        self.assertEqual(
            api.call_count,
            2,
        )

        self.assertEqual(
            len(
                api.call_args_list[0]
                .kwargs["input"]
            ),
            32,
        )

        self.assertEqual(
            result[0],
            [0.0, 1.0],
        )

        self.assertEqual(
            result[31],
            [31.0, 1.0],
        )

        self.assertEqual(
            sum(
                row["tokens_used"]
                for row in usage
            ),
            9,
        )

    @patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "test-only"},
    )
    def test_paid_usage_survives_invalid_response(self):
        from ai_assistant.bots.knowledge_utils import (
            generate_embedding_batches,
        )

        for data in [
            [],
            [
                {
                    "index": 0,
                    "embedding": [],
                }
            ],
            [
                {
                    "index": 4,
                    "embedding": [1.0],
                }
            ],
            [
                {
                    "index": 0,
                    "embedding": [
                        float("nan")
                    ],
                }
            ],
        ]:
            with self.subTest(data=data):
                usage = []

                response = self.response(1)
                response["data"] = data

                with patch(
                    "ai_assistant.bots.knowledge_utils.openai.Embedding.create",
                    return_value=response,
                ), self.assertRaises(
                    ValueError
                ):
                    generate_embedding_batches(
                        ["text"],
                        usage.append,
                    )

                self.assertEqual(
                    usage[0]["tokens_used"],
                    7,
                )

    def test_invalid_inputs_make_no_requests(self):
        from ai_assistant.bots.knowledge_utils import (
            generate_embedding_batches,
        )

        with patch(
            "ai_assistant.bots.knowledge_utils.openai.Embedding.create"
        ) as api:
            for texts in [
                [],
                [" "],
                ["x" * 8192],
            ]:
                with self.assertRaises(
                    ValueError
                ):
                    generate_embedding_batches(
                        texts,
                        lambda usage: None,
                    )

            api.assert_not_called()

    @patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "test-only"},
    )
    def test_real_batch_upload_records_one_usage_row(self):
        upload = KnowledgeUploadTests(
            methodName=(
                "test_success_saves_all_chunks_file_and_usage"
            )
        )

        upload.setUp()
        self.addCleanup(
            upload.doCleanups
        )

        request = RequestFactory().post(
            "/",
            {
                "file": SimpleUploadedFile(
                    "batch.txt",
                    b"First. Second.",
                )
            },
        )

        request.user = upload.user
        request._dont_enforce_csrf_checks = True
        request.session = {}
        request._messages = FallbackStorage(
            request
        )

        with patch(
            "ai_assistant.bots.views.chunk_text",
            return_value=[
                "First.",
                "Second.",
            ],
        ), patch(
            "ai_assistant.bots.knowledge_utils.openai.Embedding.create",
            return_value=self.response(2),
        ):
            response = bot_chat_playground(
                request,
                upload.bot.pk,
            )

        self.assertEqual(
            response.status_code,
            302,
        )

        self.assertEqual(
            BotUsageLog.objects.count(),
            1,
        )

        self.assertEqual(
            BotUsageLog.objects.get().tokens_used,
            7,
        )

        kb = KnowledgeBase.objects.exclude(
            pk=upload.existing.pk
        ).get()

        self.assertEqual(
            list(
                kb.chunks.values_list(
                    "embedding",
                    flat=True,
                )
            ),
            [
                [0.0, 1.0],
                [1.0, 1.0],
            ],
        )