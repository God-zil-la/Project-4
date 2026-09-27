"""
Live semantic tests for the category domain classifier.

Run manually with:
    python manage.py test ai_assistant.bots.test_domain_live

These tests call the configured OpenAI API.
"""

from django.contrib.auth.models import User
from django.test import TestCase

from ai_assistant.bots.knowledge_utils import check_message_domain
from ai_assistant.bots.models import Bot, KnowledgeBase, KnowledgeChunk


class LiveDomainClassifierTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="domain-live-test"
        )

    def classify(
        self,
        category,
        message,
        context="",
        filename=None,
    ):
        bot = Bot.objects.create(
            owner=self.user,
            name=(
                f"Test {category} "
                f"{Bot.objects.filter(owner=self.user).count() + 1}"
            ),
            category=category,
        )

        if filename:
            KnowledgeBase.objects.create(
                bot=bot,
                uploaded_by=self.user,
                file=f"knowledge/{filename}",
            )

        return check_message_domain(
            bot,
            message,
            conversation_context=context,
        )

    def assert_domain(
        self,
        *,
        category,
        message,
        expected,
        context="",
        filename=None,
    ):
        result = self.classify(
            category=category,
            message=message,
            context=context,
            filename=filename,
        )

        self.assertEqual(
            result["in_domain"],
            expected,
            (
                f"category={category!r}, "
                f"message={message!r}, "
                f"context={context!r}, "
                f"filename={filename!r}, "
                f"result={result!r}"
            ),
        )

    def test_education_task_context_boundaries(self):
        cases = [
            {
                "message": "Explain how a four-stroke engine works.",
                "context": (
                    "USER: I am doing a school assignment "
                    "about combustion engines."
                ),
                "expected": True,
            },
            {
                "message": "Which engine should I buy for my car?",
                "expected": False,
            },
            {
                "message": "Compare carbohydrates and protein.",
                "context": (
                    "USER: My school assignment is about nutrition."
                ),
                "expected": True,
            },
            {
                "message": "Give me a lasagna recipe.",
                "expected": False,
            },
        ]

        for case in cases:
            with self.subTest(case=case):
                self.assert_domain(
                    category="education",
                    **case,
                )

    def test_education_knowledge_file_does_not_expand_domain(self):
        self.assert_domain(
            category="education",
            message="Summarize my PDF for my assignment.",
            context=(
                "USER: My school assignment is about engines "
                "and I uploaded the source material."
            ),
            filename="motor.pdf",
            expected=True,
        )

        self.assert_domain(
            category="education",
            message="Which engine should I buy for my car?",
            filename="motor.pdf",
            expected=False,
        )

    def test_knowledge_content_resolves_document_reference(self):
        bot = Bot.objects.create(
            owner=self.user,
            name="Knowledge reference test",
            category="education",
        )

        knowledge = KnowledgeBase.objects.create(
            bot=bot,
            uploaded_by=self.user,
            file="knowledge_files/random-id.pdf",
        )

        KnowledgeChunk.objects.create(
            knowledge_file=knowledge,
            text=(
                "Deltagarhandboken 26/27. "
                "V?lkommen till Esl?vs folkh?gskola. "
                "Handboken inneh?ller information f?r deltagare "
                "om skolan och studierna."
            ),
            embedding=[0.1, 0.2, 0.3],
        )

        result = check_message_domain(
            bot,
            "kan du sammanfatta vad som st?r i deltagarhandboken",
        )

        self.assertTrue(
            result["in_domain"],
            result,
        )

        motor_bot = Bot.objects.create(
            owner=self.user,
            name="Knowledge boundary test",
            category="education",
        )

        motor_knowledge = KnowledgeBase.objects.create(
            bot=motor_bot,
            uploaded_by=self.user,
            file="knowledge_files/random-motor.pdf",
        )

        KnowledgeChunk.objects.create(
            knowledge_file=motor_knowledge,
            text=(
                "Motorhandbok. Fyrtaktsmotorer, cylindrar, "
                "br?nsleinsprutning och motorkomponenter."
            ),
            embedding=[0.1, 0.2, 0.3],
        )

        result = check_message_domain(
            motor_bot,
            "Vilken motor ska jag k?pa till min privata bil?",
        )

        self.assertFalse(
            result["in_domain"],
            result,
        )

    def test_cross_category_task_boundaries(self):
        cases = [
            {
                "category": "fitness",
                "message": (
                    "How much protein should this meal contain "
                    "after strength training?"
                ),
                "context": (
                    "USER: Help me plan meals around my "
                    "strength-training program."
                ),
                "expected": True,
            },
            {
                "category": "fitness",
                "message": "How do I bake cinnamon rolls?",
                "expected": False,
            },
            {
                "category": "tech",
                "message": (
                    "How should I validate the payment response?"
                ),
                "context": (
                    "USER: We are debugging the payment "
                    "integration in my web application."
                ),
                "expected": True,
            },
            {
                "category": "tech",
                "message": (
                    "How should I invest my retirement savings?"
                ),
                "expected": False,
            },
            {
                "category": "gardening",
                "message": (
                    "Which wood is suitable for the raised bed?"
                ),
                "context": (
                    "USER: I am building raised beds "
                    "for my vegetable garden."
                ),
                "expected": True,
            },
            {
                "category": "gardening",
                "message": "How do I renovate my entire kitchen?",
                "expected": False,
            },
            {
                "category": "hobbies",
                "message": (
                    "How does the motor weight affect "
                    "the center of gravity?"
                ),
                "context": (
                    "USER: We are setting up my RC airplane."
                ),
                "expected": True,
            },
            {
                "category": "hobbies",
                "message": "Which engine does a BMW M3 use?",
                "expected": False,
            },
        ]

        for case in cases:
            with self.subTest(case=case):
                self.assert_domain(**case)
