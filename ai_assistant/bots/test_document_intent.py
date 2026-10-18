from django.test import SimpleTestCase

from .document_intent import (
    requested_document_format,
    document_content_ready,
)


class DocumentIntentTests(SimpleTestCase):

    def test_original_workbook_request(self):
        self.assertEqual(
            requested_document_format(
                "Kan du göra en arbetsbok till mig och "
                "göra ett nedladdningsbart dokument?"
            ),
            "docx",
        )

    def test_explicit_formats(self):
        examples = {
            "Skapa en PDF": "pdf",
            "Gör ett Word-dokument": "docx",
            "Generera ett Excel-ark": "xlsx",
            "Exportera CSV": "csv",
            "Create a downloadable document": "docx",
            "Generate an Excel workbook": "xlsx",
        }

        for message, expected in examples.items():
            with self.subTest(message=message):
                self.assertEqual(
                    requested_document_format(message),
                    expected,
                )

    def test_normal_questions_do_not_generate_files(self):
        examples = (
            "Vad är en arbetsbok?",
            "Kan du förklara hur Excel fungerar?",
            "Hur skapar jag en PDF?",
            "Berätta om dokumenthantering.",
        )

        for message in examples:
            with self.subTest(message=message):
                self.assertIsNone(
                    requested_document_format(message)
                )

    def test_multiple_explicit_formats_require_selection(self):
        self.assertIsNone(
            requested_document_format(
                "Skapa både PDF och Excel"
            )
        )

    def test_short_clarification_is_not_exported(self):
        self.assertFalse(
            document_content_ready(
                "Skapa en PDF",
                "Vilket ämne ska dokumentet handla om?",
            )
        )
