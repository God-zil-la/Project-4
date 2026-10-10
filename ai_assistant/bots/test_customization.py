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

        for expected in (
            self.data["description"],
            self.data["personality"],
            "warm, friendly",
            "concise and focused",
            "Stay within this category.",
            "Verified opening hours: 10–18.",
            "RESPONSE LANGUAGE (Automatic): Answer in the language of the current user message",
            "higher-priority instructions",
    ):
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


    def test_u42_web_template_plan_visibility(self):
        url = reverse("bots:create")

        free = self.client.get(url)
        self.assertEqual(free.status_code, 200)
        self.assertContains(free, "View plans and upgrade")
        self.assertContains(free, reverse("payments:billing"))
        self.assertContains(free, 'id="id_knowledge_activation_mode"')
        self.assertNotContains(free, 'id="id_communication_style"')

        for plan in ("premium", "pro"):
            with self.subTest(plan=plan):
                self.user.profile.complimentary_plan = plan
                self.user.profile.save()
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, "View plans and upgrade")
                for field in (
                    "communication_style",
                    "response_structure",
                    "default_language",
                    "proactivity",
                    "custom_instructions",
                ):
                    self.assertContains(response, f'id="id_{field}"')

    def test_u42_free_web_blocks_advanced(self):
        from .customization import ADVANCED_CUSTOMIZATION_FIELDS

        data = {
            **self.data,
            "communication_style": "technical",
            "response_structure": "step_by_step",
            "default_language": "sv",
            "proactivity": "proactive",
            "custom_instructions": "Premium-only instruction.",
        }
        response = self.client.post(reverse("bots:create"), data)
        self.assertEqual(response.status_code, 302)
        bot = Bot.objects.get(owner=self.user)

        for field in ADVANCED_CUSTOMIZATION_FIELDS:
            self.assertEqual(
                getattr(bot, field),
                Bot._meta.get_field(field).get_default(),
            )

        form = BotForm(user=self.user)
        for field in ADVANCED_CUSTOMIZATION_FIELDS:
            self.assertNotIn(field, form.fields)

    def test_u42_free_api_rejects_advanced(self):
        from .customization import ADVANCED_CUSTOMIZATION_FIELDS

        values = {
            "communication_style": "technical",
            "response_structure": "step_by_step",
            "default_language": "sv",
            "proactivity": "proactive",
            "custom_instructions": "Premium-only instruction.",
        }
        bot = Bot.objects.create(owner=self.user, **self.data)
        url = reverse("bots:bot-detail", args=[bot.pk])

        for field in ADVANCED_CUSTOMIZATION_FIELDS:
            with self.subTest(field=field):
                response = self.api.patch(
                    url, {field: values[field]}, format="json"
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.data)

        bot.refresh_from_db()
        for field in ADVANCED_CUSTOMIZATION_FIELDS:
            self.assertEqual(
                getattr(bot, field),
                Bot._meta.get_field(field).get_default(),
            )

    def test_u42_premium_and_pro_have_advanced_access(self):
        from .customization import ADVANCED_CUSTOMIZATION_FIELDS

        for plan in ("premium", "pro"):
            with self.subTest(plan=plan):
                self.user.profile.complimentary_plan = plan
                self.user.profile.save()

                form = BotForm(user=self.user)
                for field in ADVANCED_CUSTOMIZATION_FIELDS:
                    self.assertIn(field, form.fields)

                bot = Bot.objects.create(
                    owner=self.user,
                    name=f"U42 {plan}",
                    personality="Help with travel.",
                )
                response = self.api.patch(
                    reverse("bots:bot-detail", args=[bot.pk]),
                    {"communication_style": "technical"},
                    format="json",
                )
                self.assertEqual(response.status_code, 200)
                bot.refresh_from_db()
                self.assertEqual(bot.communication_style, "technical")

    def test_u42_downgrade_disables_but_preserves(self):
        from .customization import response_preferences, response_language_rule

        self.user.profile.complimentary_plan = "premium"
        self.user.profile.save()
        bot = Bot.objects.create(
            owner=self.user,
            **self.data,
            communication_style="technical",
            default_language="sv",
            custom_instructions="Unique paid instruction.",
        )

        self.assertIn("precise technical terminology", response_preferences(bot))
        self.assertIn("Swedish", response_language_rule(bot))

        self.user.profile.complimentary_plan = "free"
        self.user.profile.save()

        self.assertNotIn("precise technical terminology", response_preferences(bot))
        self.assertNotIn("Unique paid instruction.", response_preferences(bot))
        self.assertNotIn("Swedish", response_language_rule(bot))

        bot.refresh_from_db()
        self.assertEqual(bot.communication_style, "technical")
        self.assertEqual(bot.default_language, "sv")
        self.assertEqual(bot.custom_instructions, "Unique paid instruction.")

    def test_u42_upgrade_restores_saved_preferences(self):
        from .customization import response_preferences

        self.user.profile.complimentary_plan = "premium"
        self.user.profile.save()
        bot = Bot.objects.create(
            owner=self.user,
            **self.data,
            communication_style="technical",
            custom_instructions="Restored paid instruction.",
        )

        self.user.profile.complimentary_plan = "free"
        self.user.profile.save()
        self.assertNotIn("Restored paid instruction.", response_preferences(bot))

        self.user.profile.complimentary_plan = "pro"
        self.user.profile.save()
        self.assertIn("Restored paid instruction.", response_preferences(bot))
        self.assertIn("precise technical terminology", response_preferences(bot))

    def test_advanced_customization_web_api_round_trip(self):
        self.user.profile.complimentary_plan = "premium"
        self.user.profile.save()
        preferences = {
            "communication_style": "technical",
            "response_structure": "step_by_step",
            "default_language": "sv",
            "proactivity": "balanced",
            "custom_instructions": "Explain technical concepts clearly.",
        }
        response = self.client.post(
            reverse("bots:create"),
            {**self.data, **preferences},
        )
        self.assertEqual(response.status_code, 302)

        bot = Bot.objects.get(owner=self.user)
        url = reverse("bots:bot-detail", args=[bot.pk])

        for field, value in preferences.items():
            self.assertEqual(getattr(bot, field), value)
            self.assertEqual(self.api.get(url).data[field], value)

        updated = {
            "communication_style": "formal",
            "response_structure": "paragraphs",
            "default_language": "en",
            "proactivity": "minimal",
            "custom_instructions": "Keep explanations focused.",
        }
        response = self.api.patch(url, updated, format="json")
        self.assertEqual(response.status_code, 200)

        bot.refresh_from_db()
        for field, value in updated.items():
            self.assertEqual(getattr(bot, field), value)

        response = self.client.get(reverse("bots:edit", args=[bot.pk]))
        self.assertEqual(response.status_code, 200)
        for field, value in updated.items():
            self.assertEqual(response.context["form"].initial[field], value)

    def test_advanced_customization_legacy_clients_preserve_values(self):
        preferences = {
            "communication_style": "educational",
            "response_structure": "bullet_points",
            "default_language": "sv",
            "proactivity": "proactive",
            "custom_instructions": "Give practical examples.",
        }
        bot = Bot.objects.create(
            owner=self.user,
            **self.data,
            **preferences,
        )
        url = reverse("bots:bot-detail", args=[bot.pk])

        self.assertEqual(
            self.api.patch(url, self.data, format="json").status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                reverse("bots:edit", args=[bot.pk]),
                self.data,
            ).status_code,
            302,
        )

        bot.refresh_from_db()
        for field, value in preferences.items():
            self.assertEqual(getattr(bot, field), value)

    def test_advanced_customization_invalid_choices(self):
        self.user.profile.complimentary_plan = "premium"
        self.user.profile.save()
        invalid_values = {
            "communication_style": "unknown",
            "response_structure": "unknown",
            "default_language": "unknown",
            "proactivity": "unknown",
        }

        for field, value in invalid_values.items():
            with self.subTest(field=field):
                data = {**self.data, field: value}

                web = self.client.post(reverse("bots:create"), data)
                self.assertEqual(web.status_code, 200)
                self.assertIn(field, web.context["form"].errors)

                api = self.api.post(
                    reverse("bots:bot-list-create"),
                    data,
                    format="json",
                )
                self.assertEqual(api.status_code, 400)
                self.assertIn(field, api.data)

    def test_advanced_customization_system_prompt(self):
        self.user.profile.complimentary_plan = "premium"
        self.user.profile.save()
        bot = Bot(
            owner=self.user,
            **self.data,
            communication_style="technical",
            response_structure="step_by_step",
            default_language="sv",
            proactivity="balanced",
            custom_instructions="Explain terminology before examples.",
        )

        prompt = render_system_message(bot)

        for expected in (
            "precise technical terminology",
            "numbered, step-by-step explanations",
            "Respond in Swedish from the first reply",
            "Offer relevant next steps",
            "Explain terminology before examples.",
            "This saved language is mandatory",
        ):
            self.assertIn(expected, prompt)

        self.assertIn(self.data["personality"], prompt)
        self.assertIn("Higher-priority instructions override", prompt)


    def test_proactivity_preferences_keep_questions_relevant(self):
        self.user.profile.complimentary_plan = "premium"
        self.user.profile.save()
        from .customization import response_preferences

        expectations = {
            "minimal": "without unnecessary suggestions or follow-up questions",
            "balanced": "only when clarification would materially improve the answer",
            "proactive": "one specific and relevant follow-up question",
        }
        for mode, expected in expectations.items():
            with self.subTest(mode=mode):
                bot = Bot(owner=self.user, **self.data, proactivity=mode)
                self.assertIn(expected, response_preferences(bot))
                self.assertNotIn("improvethe", response_preferences(bot))
                self.assertNotIn("relevantfollow-up", response_preferences(bot))

    def test_expanded_default_language_choices(self):
        from .customization import DEFAULT_LANGUAGE_CHOICES

        choices = dict(DEFAULT_LANGUAGE_CHOICES)

        self.assertEqual(len(DEFAULT_LANGUAGE_CHOICES), 79)
        self.assertEqual(len(choices), 79)
        self.assertTrue(all(len(code) <= 8 for code in choices))

        expected = {
            "auto": "Automatic",
            "en": "English",
            "sv": "Swedish",
            "ar": "Arabic",
            "de": "German",
            "fr": "French",
            "es": "Spanish",
            "ja": "Japanese",
            "zh-hans": "Chinese (Simplified)",
            "zh-hant": "Chinese (Traditional)",
            "pt-br": "Portuguese (Brazil)",
        }

        for code, label in expected.items():
            with self.subTest(code=code):
                self.assertEqual(choices[code], label)

    def test_expanded_languages_web_api_and_system_prompt(self):
        self.user.profile.complimentary_plan = "premium"
        self.user.profile.save()
        from .customization import DEFAULT_LANGUAGE_CHOICES

        choices = dict(DEFAULT_LANGUAGE_CHOICES)
        bot = Bot.objects.create(owner=self.user, **self.data)
        edit_url = reverse("bots:edit", args=[bot.pk])
        api_url = reverse("bots:bot-detail", args=[bot.pk])

        for language in ("af", "ar", "ja", "zh-hans", "pt-br", "de"):
            with self.subTest(language=language):
                web_response = self.client.post(
                    edit_url,
                    {**self.data, "default_language": language},
                )
                self.assertEqual(web_response.status_code, 302)

                bot.refresh_from_db()
                self.assertEqual(bot.default_language, language)

                api_response = self.api.get(api_url)
                self.assertEqual(api_response.status_code, 200)
                self.assertEqual(
                    api_response.data["default_language"], language
                )

                self.assertIn(
                    f"Respond in {choices[language]} from the first reply",
                    render_system_message(bot),
                )

        api_response = self.api.patch(
            api_url,
            {"default_language": "fr"},
            format="json",
        )
        self.assertEqual(api_response.status_code, 200)

        bot.refresh_from_db()
        self.assertEqual(bot.default_language, "fr")

        web_response = self.client.get(edit_url)
        self.assertEqual(web_response.status_code, 200)
        self.assertEqual(
            web_response.context["form"].initial["default_language"],
            "fr",
        )

        self.assertIn("Respond in French from the first reply", render_system_message(bot))

    def test_existing_conversation_uses_updated_saved_language(self):
        self.user.profile.complimentary_plan = "premium"
        self.user.profile.save()
        from .chat_service import _build_history
        from .models import Conversation, ChatMessage

        bot = Bot.objects.create(
            owner=self.user,
            **self.data,
            default_language="sv",
        )
        conversation = Conversation.objects.create(
            bot=bot,
            user=self.user,
        )

        ChatMessage.objects.create(
            conversation=conversation,
            bot=bot,
            user=self.user,
            sender=ChatMessage.SENDER_USER,
            message="Hej, hur m?r du?",
        )
        ChatMessage.objects.create(
            conversation=conversation,
            bot=bot,
            user=self.user,
            sender=ChatMessage.SENDER_ASSISTANT,
            message="Jag m?r bra, tack!",
        )

        bot.default_language = "en"
        bot.save(update_fields=["default_language"])
        bot.refresh_from_db()

        messages = _build_history(
            conversation,
            render_system_message(bot),
        )

        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("Respond in English", messages[0]["content"])
        self.assertIn(
            "When continuing an existing conversation after a language change",
            messages[0]["content"],
        )
        self.assertEqual(messages[1]["content"], "Hej, hur m?r du?")
        self.assertEqual(messages[2]["content"], "Jag m?r bra, tack!")
        self.assertEqual(
            [item["role"] for item in messages],
            ["system", "user", "assistant"],
        )

    def test_icons_in_web_list_chat_and_conversation_api(self):
        from .models import Conversation
        bot = Bot.objects.create(owner=self.user, **self.data, avatar_icon="book")
        for url in (reverse("bots:list"), reverse("bots:my-bots"), reverse("bots:playground", args=[bot.pk])):
            self.assertContains(self.client.get(url), "📚")
        conversation = Conversation.objects.create(bot=bot, user=self.user)
        response = self.api.get(reverse("bots:conversation-detail", args=[conversation.public_id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["bot_avatar_icon"], "book")
