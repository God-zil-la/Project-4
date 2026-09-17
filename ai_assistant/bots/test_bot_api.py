from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ai_assistant.bots.models import Bot


class BotAPILimitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="bot-api-user",
            password="test-password-123",
        )

        self.client = APIClient()

        self.token = Token.objects.create(
            user=self.user
        )

        self.client.credentials(
            HTTP_AUTHORIZATION=(
                f"Token {self.token.key}"
            )
        )

    def create_bot(self, name):
        return self.client.post(
            "/bots/api/bots/",
            {
                "name": name,
            },
            format="json",
        )

    def test_free_plan_allows_one_bot(self):
        response = self.create_bot(
            "Free Bot"
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        self.assertEqual(
            Bot.objects.filter(
                owner=self.user
            ).count(),
            1,
        )

    def test_free_plan_blocks_second_bot(self):
        Bot.objects.create(
            owner=self.user,
            name="Existing Bot",
        )

        response = self.create_bot(
            "Second Bot"
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertEqual(
            Bot.objects.filter(
                owner=self.user
            ).count(),
            1,
        )

    def test_complimentary_pro_allows_up_to_fifteen_bots(
        self
    ):
        profile = self.user.profile
        profile.complimentary_plan = "pro"
        profile.complimentary_until = None
        profile.save()

        for index in range(14):
            Bot.objects.create(
                owner=self.user,
                name=f"Existing Bot {index}",
            )

        response = self.create_bot(
            "Fifteenth Bot"
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        self.assertEqual(
            Bot.objects.filter(
                owner=self.user
            ).count(),
            15,
        )

    def test_complimentary_pro_blocks_sixteenth_bot(
        self
    ):
        profile = self.user.profile
        profile.complimentary_plan = "pro"
        profile.complimentary_until = None
        profile.save()

        for index in range(15):
            Bot.objects.create(
                owner=self.user,
                name=f"Existing Bot {index}",
            )

        response = self.create_bot(
            "Sixteenth Bot"
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.assertEqual(
            Bot.objects.filter(
                owner=self.user
            ).count(),
            15,
        )