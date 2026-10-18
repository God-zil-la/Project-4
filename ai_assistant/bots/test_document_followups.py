from django.test import SimpleTestCase

from .document_intent import (
    resolve_document_format,
    document_content_ready,
)


class DocumentFollowupTests(SimpleTestCase):

    def test_explicit_request(self):
        self.assertEqual(
            resolve_document_format(
                "Skapa en nedladdningsbar arbetsbok",
                [],
            ),
            "docx",
        )

    def test_followup_keeps_requested_format(self):
        history = [
            {
                "role": "user",
                "content": "Skapa en nedladdningsbar arbetsbok.",
            },
            {
                "role": "assistant",
                "content": "Vad ska arbetsboken handla om?",
            },
        ]

        self.assertEqual(
            resolve_document_format(
                "Styrketr?ning f?r nyb?rjare",
                history,
            ),
            "docx",
        )

    def test_pdf_followup(self):
        history = [
            {
                "role": "user",
                "content": "Skapa en PDF om mitt f?retag",
            },
            {
                "role": "assistant",
                "content": "Vilket ?mne vill du fokusera p??",
            },
        ]

        self.assertEqual(
            resolve_document_format(
                "Marknadsf?ring",
                history,
            ),
            "pdf",
        )

    def test_no_unrelated_document(self):
        history = [
            {
                "role": "user",
                "content": "Hej!",
            },
            {
                "role": "assistant",
                "content": "Vad vill du g?ra?",
            },
        ]

        self.assertIsNone(
            resolve_document_format("Tr?ning", history)
        )

    def test_cancel_pending_document(self):
        history = [
            {
                "role": "user",
                "content": "Skapa en PDF",
            },
            {
                "role": "assistant",
                "content": "Vad ska den handla om?",
            },
        ]

        self.assertIsNone(
            resolve_document_format("Avbryt", history)
        )

    def test_no_replay_without_clarification(self):
        history = [
            {
                "role": "user",
                "content": "Skapa en PDF",
            },
            {
                "role": "assistant",
                "content": "H?r kommer texten.",
            },
        ]

        self.assertIsNone(
            resolve_document_format("Tack", history)
        )

    def test_no_export_of_short_question(self):
        self.assertFalse(
            document_content_ready(
                "Skapa en PDF",
                "Vilket ?mne vill du att jag ska skriva om?",
            )
        )
