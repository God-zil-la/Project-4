import uuid
from unittest.mock import Mock, patch
from datetime import datetime, timezone

from django.test import SimpleTestCase
from django.urls import reverse, resolve
from rest_framework.test import APIRequestFactory, force_authenticate


class ConversationDocumentListTests(SimpleTestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = Mock(pk=101, is_authenticated=True)
        self.conversation_id = uuid.uuid4()

    def call(self, user):
        path = reverse(
            "bots:conversation-documents",
            kwargs={"conversation_id": self.conversation_id},
        )
        request = self.factory.get(path)
        if user is not None:
            force_authenticate(request, user=user)
        match = resolve(path)
        return match.func(request, **match.kwargs)

    @patch("ai_assistant.bots.document_list_api.GeneratedDocument.objects.filter")
    @patch("ai_assistant.bots.document_list_api.get_object_or_404")
    def test_owner_gets_documents(self, get_object, filter_docs):
        conversation = Mock()
        conversation.bot = Mock()
        conversation.public_id = self.conversation_id
        get_object.return_value = conversation

        document = Mock()
        document.pk = uuid.uuid4()
        document.filename = "document.pdf"
        document.file_format = "pdf"
        document.size_bytes = 1234
        document.created_at = datetime.now(timezone.utc)
        filter_docs.return_value.order_by.return_value = [document]

        response = self.call(self.user)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["documents"]), 1)
        self.assertEqual(response.data["documents"][0]["format"], "pdf")
        self.assertEqual(response["Cache-Control"], "no-store")

        conversation_filters = get_object.call_args.kwargs
        self.assertEqual(conversation_filters["user"], self.user)
        self.assertEqual(conversation_filters["bot__owner"], self.user)
        self.assertIs(conversation_filters["is_widget"], False)

        doc_filters = filter_docs.call_args.kwargs
        self.assertEqual(doc_filters["owner"], self.user)
        self.assertIs(doc_filters["conversation"], conversation)

    @patch("ai_assistant.bots.document_list_api.get_object_or_404")
    def test_anonymous_denied(self, get_object):
        response = self.call(None)
        self.assertIn(response.status_code, (401, 403))
        get_object.assert_not_called()

    @patch("ai_assistant.bots.document_list_api.get_object_or_404")
    def test_unknown_or_unowned_conversation_denied(self, get_object):
        from django.http import Http404
        get_object.side_effect = Http404()

        response = self.call(self.user)

        self.assertEqual(response.status_code, 404)
