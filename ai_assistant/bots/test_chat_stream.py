"""Credential-free transport tests; the existing service is always mocked."""
import json
from threading import BoundedSemaphore, Event
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.http import Http404, JsonResponse
from django.test import RequestFactory, SimpleTestCase

from . import chat_stream, views
from .chat_service import ChatRateLimitError, ChatServiceError, ChatUsageLimitError


class ChatStreamTests(SimpleTestCase):
    def setUp(self):
        self.slots = BoundedSemaphore(2)
        slot_patch = patch.object(chat_stream, "_slots", self.slots)
        slot_patch.start()
        self.addCleanup(slot_patch.stop)

    def test_heartbeat_before_completion_and_unicode_once(self):
        release = Event()
        self.addCleanup(release.set)
        text = "မင်္ဂလာပါ " * 2000
        def process():
            self.assertTrue(release.wait(2))
            return JsonResponse({"reply": text})
        process = Mock(side_effect=process)
        with patch.object(chat_stream, "HEARTBEAT_SECONDS", 0.001):
            response = chat_stream.stream_chat_response(process)
            iterator = iter(response.streaming_content)
            self.assertEqual(json.loads(next(iterator))["type"], "heartbeat")
            self.assertEqual(json.loads(next(iterator))["type"], "heartbeat")
            release.set()
            events = [json.loads(chunk) for chunk in iterator]
        results = [event for event in events if event["type"] == "result"]
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["data"]["reply"], text)
        process.assert_called_once()
        self.assertIn("no-transform", response["Cache-Control"])
        response.close()

    def test_disconnect_does_not_restart_processing_or_free_busy_slot_early(self):
        release, finished = Event(), Event()
        self.addCleanup(release.set)
        def process():
            release.wait(2)
            return JsonResponse({"reply": "done"})
        process = Mock(side_effect=process)
        with patch.object(chat_stream.connections, "close_all", side_effect=finished.set):
            response = chat_stream.stream_chat_response(process)
            next(iter(response.streaming_content))
            response.close()
            self.assertTrue(self.slots.acquire(False))
            self.assertFalse(self.slots.acquire(False))
            rejected = Mock()
            self.assertEqual(chat_stream.stream_chat_response(rejected).status_code, 503)
            rejected.assert_not_called()
            release.set()
            self.assertTrue(finished.wait(2))
        process.assert_called_once()
        self.slots.release()

    def test_unexpected_error_is_terminal_and_releases_resources(self):
        with patch.object(chat_stream.connections, "close_all") as close:
            response = chat_stream.stream_chat_response(Mock(side_effect=ValueError("failure")))
            events = [json.loads(chunk) for chunk in response.streaming_content]
        self.assertEqual(events[-1]["status"], 500)
        close.assert_called_once()
        self.assertTrue(self.slots.acquire(False))
        self.assertTrue(self.slots.acquire(False))
        response.close()


class AjaxChatTransportTests(SimpleTestCase):
    def setUp(self):
        self.user = SimpleNamespace(is_authenticated=True)
        self.bot = object()

    def request(self, stream=True, csrf=True, body=None):
        request = RequestFactory().post('/bots/298/ajax_chat/',
            data=json.dumps(body or {"message": "မင်္ဂလာပါ", "conversation_id": "existing"}),
            content_type="application/json",
            HTTP_ACCEPT="application/x-ndjson" if stream else "application/json")
        request.user = self.user
        request._dont_enforce_csrf_checks = csrf
        return request

    def call(self, error=None, stream=True):
        result = dict(response="မင်္ဂလာပါ", conversation_id="existing", plan="pro",
                      monthly_messages_used=1, monthly_limit=100, in_domain=True)
        with patch.object(views, "get_object_or_404", return_value=self.bot) as owner, \
             patch.object(views, "process_bot_message", return_value=result, side_effect=error) as process:
            response = views.ajax_chat(self.request(stream=stream), 298)
            if response.streaming:
                event = [json.loads(chunk) for chunk in response.streaming_content][-1]
                self.assertEqual(event.pop("type"), "result")
            else:
                event = {"status": response.status_code, "data": json.loads(response.content)}
            owner.assert_called_once_with(views.Bot, id=298, owner=self.user)
            process.assert_called_once_with(user=self.user, bot=self.bot,
                message="မင်္ဂလာပါ", conversation="existing")
            response.close()
            return event

    def test_success_matches_legacy_json(self):
        self.assertEqual(self.call(), self.call(stream=False))

    def test_service_errors_keep_status_and_payload(self):
        errors = [
            ChatUsageLimitError("Quota", {"plan": "pro", "monthly_message_limit_reached": True,
                "monthly_messages_used": 100, "monthly_message_limit": 100}),
            ChatRateLimitError("Wait", 12), ChatServiceError("Invalid conversation"),
            RuntimeError("Provider failed"),
        ]
        for error, status in zip(errors, [403, 429, 400, 500]):
            with self.subTest(status=status):
                event = self.call(error)
                self.assertEqual(event["status"], status)
                self.assertEqual(event, self.call(error, stream=False))

    def test_auth_csrf_owner_and_empty_input_never_start_ai(self):
        with patch.object(views, "process_bot_message") as process:
            request = self.request()
            request.user = SimpleNamespace(is_authenticated=False)
            self.assertEqual(views.ajax_chat(request, 298).status_code, 302)
            self.assertEqual(views.ajax_chat(self.request(csrf=False), 298).status_code, 403)
            with patch.object(views, "get_object_or_404", side_effect=Http404):
                response = views.ajax_chat(self.request(), 298)
                self.assertGreaterEqual(response.status_code, 400)
                self.assertFalse(response.streaming)
            with patch.object(views, "get_object_or_404", return_value=self.bot):
                self.assertEqual(views.ajax_chat(self.request(body={"message": " "}), 298).status_code, 400)
            process.assert_not_called()
