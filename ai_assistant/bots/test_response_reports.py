from datetime import timedelta

from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import AIResponseReport, Bot, ChatMessage, Conversation


class ResponseReportTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reporter")
        self.other = User.objects.create_user(username="other")
        self.bot = Bot.objects.create(owner=self.user, name="Assistant")
        self.conversation = Conversation.objects.create(user=self.user, bot=self.bot)
        self.message = self.make_message()
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {Token.objects.create(user=self.user).key}")

    def make_message(self, **overrides):
        return ChatMessage.objects.create(**{
            "bot": self.bot, "user": self.user, "conversation": self.conversation,
            "sender": "assistant", "message": "Response to review", **overrides,
        })

    def url(self, message=None, conversation=None):
        return reverse("bots:ai-response-report", kwargs={
            "conversation_id": (conversation or self.conversation).public_id,
            "message_id": (message or self.message).pk,
        })

    def report(self, message=None):
        return self.client.post(self.url(message), {}, format="json")

    def test_authenticated_report_snapshots_server_evidence_and_is_idempotent(self):
        first = self.report()
        self.assertEqual(first.status_code, 201)
        report = AIResponseReport.objects.get()
        self.assertEqual(report.reporter, self.user)
        self.assertEqual(report.response_text, self.message.message)
        self.assertEqual(report.response_created_at, self.message.timestamp)
        self.assertEqual(report.conversation_id_snapshot, self.conversation.public_id)
        self.assertEqual(report.original_message_id, self.message.pk)
        self.assertEqual(report.status, "pending")
        second = self.report()
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data, second.data)
        self.assertEqual(AIResponseReport.objects.count(), 1)
        self.assertEqual(ChatMessage.objects.count(), 1)

    def test_requires_authentication(self):
        self.client.credentials()
        self.assertEqual(self.report().status_code, 401)
        self.assertFalse(AIResponseReport.objects.exists())

    def test_other_users_and_staff_cannot_report_inaccessible_responses(self):
        self.other.is_staff = True
        self.other.save()
        self.client.force_authenticate(self.other)
        self.assertEqual(self.report().status_code, 404)
        self.assertFalse(AIResponseReport.objects.exists())

    def test_rejects_user_legacy_missing_and_wrong_conversation_messages(self):
        for message in [self.make_message(sender="user"), self.make_message(conversation=None)]:
            self.assertEqual(self.report(message).status_code, 404)
        second = Conversation.objects.create(user=self.user, bot=self.bot)
        self.assertEqual(self.client.post(self.url(conversation=second), {}, format="json").status_code, 404)
        url = self.url().replace(f"messages/{self.message.pk}/", "messages/999999/")
        self.assertEqual(self.client.post(url, {}, format="json").status_code, 404)
        self.assertFalse(AIResponseReport.objects.exists())

    def test_visible_widget_response_can_be_reported_by_conversation_owner(self):
        self.conversation.is_widget = True
        self.conversation.save()
        self.assertEqual(self.report().status_code, 201)

    def test_rejects_invalid_or_client_supplied_evidence(self):
        for payload in [[], "text", {"response_text": "forged"}, {"reporter": self.other.pk}, {"status": "reviewed"}]:
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post(self.url(), payload, format="json").status_code, 400)
        self.assertEqual(self.client.post(self.url(), '{', content_type="application/json").status_code, 400)
        self.assertFalse(AIResponseReport.objects.exists())

    def test_daily_limit_duplicate_retry_and_expiry(self):
        self.assertEqual(self.report().status_code, 201)
        for _ in range(19):
            self.assertEqual(self.report(self.make_message()).status_code, 201)
        self.assertEqual(self.report().status_code, 200)
        next_message = self.make_message()
        response = self.report(next_message)
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertEqual(AIResponseReport.objects.count(), 20)
        AIResponseReport.objects.update(created_at=timezone.now() - timedelta(days=1, seconds=1))
        self.assertEqual(self.report(next_message).status_code, 201)

    def test_database_unique_constraint(self):
        self.report()
        report = AIResponseReport.objects.get()
        report.pk = None
        with self.assertRaises(IntegrityError), transaction.atomic():
            report.save(force_insert=True)

    def test_evidence_survives_conversation_and_account_deletion(self):
        self.report()
        self.conversation.delete()
        self.user.delete()
        report = AIResponseReport.objects.get()
        self.assertIsNone(report.message_id)
        self.assertIsNone(report.reporter_id)
        self.assertEqual(report.response_text, "Response to review")

    def test_admin_review_is_audited_and_evidence_is_read_only(self):
        self.report()
        report = AIResponseReport.objects.get()
        staff = User.objects.create_superuser("reviewer", "reviewer@example.test", "test-password")
        self.client.force_login(staff)
        url = reverse("admin:bots_airesponsereport_change", args=[report.pk])
        response = self.client.post(url, {"status": "reviewed", "review_notes": "Investigated", "response_text": "tampered", "_save": "Save"})
        self.assertEqual(response.status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.status, "reviewed")
        self.assertEqual(report.review_notes, "Investigated")
        self.assertEqual(report.response_text, "Response to review")
        self.assertTrue(LogEntry.objects.filter(user=staff, object_id=str(report.pk), action_flag=2).exists())
        model_admin = admin.site._registry[AIResponseReport]
        self.assertFalse(model_admin.has_add_permission(None))
        self.assertFalse(model_admin.has_delete_permission(None, report))

    def test_no_public_report_listing_or_mutation(self):
        self.report()
        for method in (self.client.get, self.client.patch, self.client.delete):
            self.assertEqual(method(self.url()).status_code, 405)
