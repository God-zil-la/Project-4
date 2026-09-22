"""Create/edit guidance and existing cross-client configuration contract."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .forms import BotForm
from .knowledge_utils import render_system_message
from .models import Bot
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from unittest.mock import patch
from .assistant_validation import save_assistant, DUPLICATE_NAME
from .customization import response_preferences


class AssistantCustomizationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="customization")
        self.client.force_login(self.user)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.data = {
            "name": "Weekend guide",
            "description": "Help families plan weekend trips.",
            "personality": "Be friendly. Ask about the budget first.",
            "category": "travel",
        }

    def test_create_and_edit_show_help_linked_to_inputs(self):
        bot = Bot.objects.create(owner=self.user, **self.data)
        for url in (reverse("bots:create"), reverse("bots:edit", args=[bot.pk])):
            # A second assistant is allowed so create remains accessible.
            self.user.profile.complimentary_plan = "pro"
            self.user.profile.save()
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "Personality &amp; instructions")
            for field in ("description", "personality"):
                self.assertContains(response, BotForm().fields[field].help_text)
                self.assertContains(response, f'id="id_{field}_helptext"')
                self.assertContains(response, f'aria-describedby="id_{field}_helptext"')

    def test_web_create_api_read_and_update_web_edit_preserve_configuration(self):
        response = self.client.post(reverse("bots:create"), self.data)
        self.assertEqual(response.status_code, 302)
        bot = Bot.objects.get(owner=self.user)
        api_url = reverse("bots:bot-detail", args=[bot.pk])
        for key, value in self.data.items():
            self.assertEqual(self.api.get(api_url).data[key], value)

        updated = {**self.data, "personality": "Be concise. Ask one question at a time."}
        response = self.api.patch(api_url, updated, format="json")
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("bots:edit", args=[bot.pk]))
        self.assertEqual(response.context["form"].initial["personality"], updated["personality"])
        updated["description"] = ""
        response = self.client.post(reverse("bots:edit", args=[bot.pk]), updated)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.api.get(api_url).data["description"], "")
        self.assertEqual(self.api.get(api_url).data["personality"], updated["personality"])
        bot.refresh_from_db()
        self.assertIn(updated["personality"], render_system_message(bot))

    def test_invalid_form_keeps_input_and_guidance(self):
        response = self.client.post(reverse("bots:create"), {**self.data, "name": ""})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Bot.objects.filter(owner=self.user).exists())
        self.assertContains(response, self.data["personality"])
        self.assertContains(response, BotForm().fields["description"].help_text)

    def test_edit_rejects_another_owners_assistant(self):
        other = User.objects.create_user(username="other-owner")
        bot = Bot.objects.create(owner=other, **self.data)
        self.assertEqual(self.client.post(reverse("bots:edit", args=[bot.pk]), self.data).status_code, 404)
        self.assertEqual(self.api.patch(reverse("bots:bot-detail", args=[bot.pk]), self.data, format="json").status_code, 404)

    def test_web_api_validation_parity(self):
        cases = [
            ("name", ""), ("name", "   "), ("name", "x" * 101),
            ("personality", ""), ("personality", " \n "),
            ("category", "invalid"), ("response_tone", "loud"),
            ("response_length", "unlimited"), ("avatar_icon", "https://example.test/icon"),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                data = {**self.data, field: value}
                web = self.client.post(reverse("bots:create"), data)
                api = self.api.post(reverse("bots:bot-list-create"), data, format="json")
                self.assertEqual(web.status_code, 200)
                self.assertIn(field, web.context["form"].errors)
                self.assertEqual(api.status_code, 400)
                self.assertIn(field, api.data)
                self.assertFalse(Bot.objects.filter(owner=self.user).exists())

    def test_json_invalid_types_cannot_become_configuration(self):
        for field in ("name", "description", "personality", "category", "response_tone", "response_length", "avatar_icon"):
            for value in (None, [], {}, True, 12):
                with self.subTest(field=field, value=value):
                    result = self.api.post(reverse("bots:bot-list-create"), {**self.data, field: value}, format="json")
                    self.assertEqual(result.status_code, 400)
                    self.assertIn(field, result.data)

    def test_duplicate_edit_is_field_error_and_preserves_database(self):
        existing = Bot.objects.create(owner=self.user, **self.data)
        other = Bot.objects.create(owner=self.user, name="Second", personality="Keep this")
        data = {**self.data, "name": "  Weekend guide  "}
        web = self.client.post(reverse("bots:edit", args=[other.pk]), data)
        api = self.api.patch(reverse("bots:bot-detail", args=[other.pk]), data, format="json")
        self.assertEqual(web.status_code, 200)
        self.assertEqual(list(web.context["form"].errors["name"]), [DUPLICATE_NAME])
        self.assertEqual(api.status_code, 400)
        self.assertEqual(api.data["name"], [DUPLICATE_NAME])
        other.refresh_from_db()
        self.assertEqual((other.name, other.personality), ("Second", "Keep this"))
        self.assertEqual(self.client.post(reverse("bots:edit", args=[existing.pk]), self.data).status_code, 302)

    def test_same_name_for_different_owners_is_allowed(self):
        other = User.objects.create_user(username="different-owner")
        Bot.objects.create(owner=other, **self.data)
        self.assertEqual(self.api.post(reverse("bots:bot-list-create"), self.data, format="json").status_code, 201)

    def test_text_is_trimmed_and_description_can_be_cleared(self):
        data = {**self.data, "name": "  😀 " , "description": "  details  ", "personality": "  Keep it clear. \n"}
        self.client.post(reverse("bots:create"), data)
        bot = Bot.objects.get(owner=self.user)
        self.assertEqual((bot.name, bot.description, bot.personality), ("😀", "details", "Keep it clear."))
        result = self.api.patch(reverse("bots:bot-detail", args=[bot.pk]), {"name": " 😀 ", "description": "  "}, format="json")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["description"], "")
        self.assertEqual(result.data["personality"], "Keep it clear.")

    def test_preferences_round_trip_and_old_clients_preserve_them(self):
        data = {**self.data, "response_tone": "professional", "response_length": "detailed", "avatar_icon": "book"}
        self.assertEqual(self.client.post(reverse("bots:create"), data).status_code, 302)
        bot = Bot.objects.get(owner=self.user)
        url = reverse("bots:bot-detail", args=[bot.pk])
        for key, value in data.items():
            self.assertEqual(self.api.get(url).data[key], value)
        # A v4 client sends only its original four fields.
        self.assertEqual(self.api.patch(url, self.data, format="json").status_code, 200)
        self.assertEqual(self.client.post(reverse("bots:edit", args=[bot.pk]), self.data).status_code, 302)
        for key in ("response_tone", "response_length", "avatar_icon"):
            self.assertEqual(self.api.get(url).data[key], data[key])
        reset = {key: "default" for key in ("response_tone", "response_length", "avatar_icon")}
        self.assertEqual(self.api.patch(url, reset, format="json").status_code, 200)
        bot.refresh_from_db()
        self.assertEqual(response_preferences(bot), "")
        self.assertEqual(bot.avatar_symbol, "")

    def test_defaults_match_for_web_and_api_create(self):
        for client, url in ((self.client, reverse("bots:create")), (self.api, reverse("bots:bot-list-create"))):
            client.post(url, {"name": "Defaults"})
            bot = Bot.objects.get(owner=self.user)
            self.assertEqual(bot.category, "general")
            self.assertEqual(bot.personality, "I am a helpful and friendly assistant.")
            self.assertEqual((bot.response_tone, bot.response_length, bot.avatar_icon), ("default",) * 3)
            self.assertNotIn("DEFAULT RESPONSE PREFERENCES", render_system_message(bot))
            bot.delete()

    def test_prompt_preferences_preserve_configured_text_and_rules(self):
        bot = Bot(**self.data, response_tone="friendly", response_length="concise", avatar_icon="book")
        prompt = render_system_message(bot, "Verified opening hours: 10–18.")
        for expected in (self.data["description"], self.data["personality"], "warm, friendly", "concise and focused", "Stay within this category.", "Verified opening hours: 10–18.", "Answer in the language the user is using", "more specific response style"):
            self.assertIn(expected, prompt)
        self.assertNotIn("📚", prompt)
        self.assertEqual(bot.personality, self.data["personality"])

    def test_all_plans_can_use_controls_with_existing_creation_limits(self):
        for plan, limit in (("free", 1), ("premium", 5), ("pro", 15)):
            with self.subTest(plan=plan):
                Bot.objects.filter(owner=self.user).delete()
                profile = self.user.profile
                profile.complimentary_plan = plan if plan != "free" else ""
                profile.save()
                response = self.api.post(reverse("bots:bot-list-create"), {**self.data, "response_tone": "professional", "avatar_icon": "robot"}, format="json")
                self.assertEqual(response.status_code, 201)
                for index in range(limit - 1):
                    Bot.objects.create(owner=self.user, name=f"Existing {index}")
                self.assertEqual(self.api.post(reverse("bots:bot-list-create"), {"name": "Over limit"}, format="json").status_code, 403)
                self.assertEqual(self.client.post(reverse("bots:create"), {"name": "Over limit"}).status_code, 302)
                self.assertEqual(Bot.objects.filter(owner=self.user).count(), limit)

    def test_duplicate_database_conflict_becomes_validation_error(self):
        Bot.objects.create(owner=self.user, **self.data)
        with self.assertRaisesMessage(ValidationError, DUPLICATE_NAME):
            save_assistant(Bot(owner=self.user, **self.data))
        with patch.object(Bot, "save", side_effect=IntegrityError("unrelated database error")):
            with self.assertRaises(IntegrityError):
                save_assistant(Bot(owner=self.user, name="Unique"))

    def test_icons_in_web_list_chat_and_conversation_api(self):
        from .models import Conversation
        bot = Bot.objects.create(owner=self.user, **self.data, avatar_icon="book")
        for url in (reverse("bots:list"), reverse("bots:my-bots"), reverse("bots:playground", args=[bot.pk])):
            self.assertContains(self.client.get(url), "📚")
        conversation = Conversation.objects.create(bot=bot, user=self.user)
        response = self.api.get(reverse("bots:conversation-detail", args=[conversation.public_id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["bot_avatar_icon"], "book")
