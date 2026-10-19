from django.test import SimpleTestCase

from .document_ai_intent import is_document_clarification


class DocumentRecoveryGuardTests(SimpleTestCase):
    def test_sweden_clarification_is_preserved(self):
        self.assertTrue(is_document_clarification("Vilket ämne ska dokumentet handla om?"))

    def test_english_clarification_is_preserved(self):
        self.assertTrue(is_document_clarification("What should the file contain?"))

    def test_arabic_clarification_is_preserved(self):
        self.assertTrue(is_document_clarification("ما موضوع الملف؟"))

    def test_refusal_is_not_a_clarification(self):
        self.assertFalse(is_document_clarification("I cannot create downloadable files."))

    def test_document_with_final_question_is_not_clarification(self):
        self.assertFalse(is_document_clarification("# Guide\n\nContent of the guide.\n\nAny questions?"))
