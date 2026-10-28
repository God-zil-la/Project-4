from uuid import uuid4
from django.test import SimpleTestCase
from .errors import InvalidInput
from .validation import validate


class ValidationTests(SimpleTestCase):
    def check(self, text, **kwargs):
        return validate(text=text, assistant_id=kwargs.get('assistant_id', 1),
                        request_id=kwargs.get('request_id', uuid4()))

    def test_boundaries(self):
        self.check('a' * 4000)
        self.check('\U0001f600' * 4000)  # Exactly 16,000 UTF-8 bytes.
        for text in ('a' * 4001, '\U0001f600' * 4001):
            with self.assertRaises(InvalidInput):
                self.check(text)

    def test_invalid_text(self):
        for text in (None, 12, b'text', '', ' \n\t', '\ud800', 'hello\x00', 'hello\x01'):
            with self.subTest(text=repr(text)), self.assertRaises(InvalidInput):
                self.check(text)

    def test_ssml_and_markup_rejected(self):
        for text in ('<speak>hi</speak>', '<break time="1s"/>', '<SPEAK/>', '<!--x-->', '<?xml?>'):
            with self.subTest(text=text), self.assertRaises(InvalidInput):
                self.check(text)

    def test_plain_text_unicode_and_comparisons(self):
        self.check('Hej! 日本語 👋\n2 < 3 & 5 > 4')

    def test_invalid_identifiers(self):
        for value in (True, 0, -1, '1', None):
            with self.assertRaises(InvalidInput):
                self.check('hello', assistant_id=value)
        with self.assertRaises(InvalidInput):
            self.check('hello', request_id='bad')

    def test_fingerprint_binds_exact_text_and_assistant(self):
        _, first = self.check('hello')
        self.assertEqual(first, self.check('hello')[1])
        self.assertNotEqual(first, self.check('hello ')[1])
        self.assertNotEqual(first, self.check('hello', assistant_id=2)[1])
