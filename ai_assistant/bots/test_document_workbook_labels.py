from django.test import SimpleTestCase
from .document_workbook_validation import extract_amounts


class WorkbookSourceLabelTests(SimpleTestCase):

    def test_quoted_sheet_prefix_is_removed(self):
        message = (
            'Create an Excel workbook with three worksheets. '
            'Sheet 1 "Monthly Budget": Rent 15000, Staff 25000, '
            'Materials 10000 and Other 5000 SEK. '
            'Sheet 2 "Sales Forecast": January through December, '
            '50000 SEK each month.'
        )

        actual = [
            (item["value"], item["label"], item["count"])
            for item in extract_amounts(message)
        ]

        self.assertEqual(actual, [
            ("15000", "Rent", 1),
            ("25000", "Staff", 1),
            ("10000", "Materials", 1),
            ("5000", "Other", 1),
            ("50000", "", 12),
        ])

    def test_normal_labels_remain_unchanged(self):
        amounts = extract_amounts("Rent 15000, Staff 25000")

        self.assertEqual(
            [(a["value"], a["label"]) for a in amounts],
            [("15000", "Rent"), ("25000", "Staff")],
        )
