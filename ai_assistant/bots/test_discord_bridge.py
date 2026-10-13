"""Offline bridge and downloaded configuration regression tests."""
import asyncio
import io
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import requests
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ai_assistant.static.discord_bridge import bridge
from ai_assistant.static.discord_bridge.backend_url import normalize_backend_url
from .chat_service import _resolve_conversation
from .discord_auth import issue_discord_integration
from .models import Bot, Conversation, DiscordIntegration

CONFIG = {"DISCORD_TOKEN": "test-discord", "DJANGO_API_TOKEN": "test-integration",
          "DJANGO_BOT_ID": "7", "DJANGO_BACKEND": "https://example.test"}


class BridgeConfigurationTests(SimpleTestCase):
    def test_bridge_and_helper_compile(self):
        for filename in ("bridge.py", "backend_url.py"):
            path = Path(bridge.__file__).with_name(filename)
            compile(path.read_bytes(), str(path), "exec")

    def test_required_configuration(self):
        with patch.object(bridge, "load_dotenv"), patch.dict(os.environ, CONFIG, clear=True):
            self.assertEqual(bridge.load_config(), CONFIG)
            for name in CONFIG:
                with patch.dict(os.environ, {name: ""}):
                    with self.assertRaises(ValueError):
                        bridge.load_config()
            with patch.dict(os.environ, {"DJANGO_BOT_ID": "../7"}):
                with self.assertRaises(ValueError):
                    bridge.load_config()

    def test_backend_origins_normalize(self):
        for value in ("example.test", "https://example.test", "https://EXAMPLE.test/", " example.test "):
            self.assertEqual(normalize_backend_url(value), "https://example.test")
        self.assertEqual(normalize_backend_url("example.test:8443/"), "https://example.test:8443")

    def test_unsafe_backend_values_rejected(self):
        for value in ("", "http://example.test", "https://user:secret@example.test",
                      "https://example.test/path", "example.test?secret=x", "example.test#fragment",
                      "example.test\nINJECT=x", "https://https://example.test", "example.test:0",
                      "example.test:65536", "example.test:", "example.test\\other", "bad host.test"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_backend_url(value)

    def test_request_contract_and_continuation(self):
        conversation_id = str(uuid4())
        response = Mock(status_code=200)
        response.json.return_value = {"response": "Hej!", "conversation_id": conversation_id}
        with patch.object(bridge.requests, "post", return_value=response) as post:
            self.assertEqual(bridge.request_ai(CONFIG, "Hello"), ("Hej!", conversation_id))
            post.assert_called_once_with(
                "https://example.test/bots/api/discord/bot/7/chat/",
                headers={"Authorization": "Discord test-integration"}, json={"message": "Hello"},
                timeout=(5, 60), allow_redirects=False)
            bridge.request_ai(CONFIG, "Again", conversation_id)
            self.assertEqual(post.call_args.kwargs["json"], {"message": "Again", "conversation_id": conversation_id})
        self.assertEqual(response.close.call_count, 2)

    def test_http_errors_do_not_expose_response_or_configuration(self):
        for status in (301, 401, 403, 404, 429, 500):
            response = Mock(status_code=status, text="SECRET RESPONSE")
            with patch.object(bridge.requests, "post", return_value=response):
                with self.assertRaises(bridge.BridgeError) as caught:
                    bridge.request_ai(CONFIG, "hello")
            self.assertNotIn("SECRET", str(caught.exception))
            self.assertNotIn(CONFIG["DJANGO_API_TOKEN"], str(caught.exception))
            response.json.assert_not_called()
            response.close.assert_called_once()

    def test_network_errors_are_sanitized(self):
        for error in (requests.Timeout("SECRET"), requests.ConnectionError("SECRET")):
            with patch.object(bridge.requests, "post", side_effect=error):
                with self.assertRaises(bridge.BridgeError) as caught:
                    bridge.request_ai(CONFIG, "hello")
            self.assertNotIn("SECRET", str(caught.exception))

    def test_invalid_response_rejected(self):
        for data in (None, [], {}, {"response": ""}, {"response": "ok", "conversation_id": "bad"},
                     {"response": 5, "conversation_id": str(uuid4())}):
            response = Mock(status_code=200)
            response.json.return_value = data
            with patch.object(bridge.requests, "post", return_value=response):
                with self.assertRaises(bridge.BridgeError):
                    bridge.request_ai(CONFIG, "hello")
        response.json.side_effect = ValueError("SECRET malformed JSON")
        with patch.object(bridge.requests, "post", return_value=response):
            with self.assertRaises(bridge.BridgeError):
                bridge.request_ai(CONFIG, "hello")
        response.json.side_effect = None
        response.json.return_value = {"response": "ok", "conversation_id": str(uuid4())}
        with patch.object(bridge.requests, "post", return_value=response):
            with self.assertRaises(bridge.BridgeError):
                bridge.request_ai(CONFIG, "hello", str(uuid4()))

    def test_unicode_chunking_preserves_content_and_limit(self):
        for text in ("a" * 4001, "😀" * 2001, "å\n" * 2000, "", "@everyone " * 500):
            chunks = list(bridge.split_reply(text))
            self.assertEqual("".join(chunks), text)
            self.assertTrue(all(0 < len(chunk.encode("utf-16-le")) // 2 <= 2000 for chunk in chunks))


class BridgeAsyncTests(IsolatedAsyncioTestCase):
    async def test_context_persistence_isolation_and_serialization(self):
        state = bridge.ConversationState()
        ids = [str(uuid4()), str(uuid4()), str(uuid4())]
        async def worker(function, config, message, conversation):
            await asyncio.sleep(0)
            return "ok", conversation or ids.pop(0)
        with patch.object(bridge.asyncio, "to_thread", side_effect=worker) as thread:
            await asyncio.gather(state.answer(CONFIG, (1, 10), "first"), state.answer(CONFIG, (1, 10), "second"))
            await state.answer(CONFIG, (1, 11), "thread")
            await state.answer(CONFIG, (None, 12), "DM")
            calls = thread.call_args_list
            self.assertIsNone(calls[0].args[3])
            self.assertEqual(calls[1].args[3], state.conversations[(1, 10)])
            self.assertIsNone(calls[2].args[3])
            self.assertIsNone(calls[3].args[3])
            self.assertEqual(len(set(state.conversations.values())), 3)
            self.assertIs(calls[0].args[0], bridge.request_ai)

    async def test_conflicting_conversation_and_failed_requests_not_cached(self):
        state = bridge.ConversationState()
        cid = str(uuid4())
        state.conversations[(1, 1)] = cid
        with patch.object(bridge.asyncio, "to_thread", new=AsyncMock(return_value=("ok", cid))):
            with self.assertRaises(bridge.BridgeError):
                await state.answer(CONFIG, (1, 2), "hello")
        with patch.object(bridge.asyncio, "to_thread", new=AsyncMock(side_effect=bridge.BridgeError("safe"))):
            with self.assertRaises(bridge.BridgeError):
                await state.answer(CONFIG, (1, 3), "hello")
        self.assertEqual(state.conversations, {(1, 1): cid})

    async def test_triggers_ignore_bots_ping_mentions_and_dm(self):
        bot = bridge.create_bot(CONFIG)
        bot._connection.user = SimpleNamespace(id=99, bot=True)
        channel = SimpleNamespace(id=12, send=AsyncMock())
        message = SimpleNamespace(content="ordinary text", author=SimpleNamespace(bot=False),
                                  guild=SimpleNamespace(id=1), channel=channel)
        with patch.object(bridge.ConversationState, "answer", new=AsyncMock(return_value="reply")) as answer:
            await bot.on_message(message)
            answer.assert_not_awaited()
            message.content = "!ask Hello"
            message.author.bot = True
            await bot.on_message(message)
            answer.assert_not_awaited()
            message.author.bot = False
            await bot.on_message(message)
            answer.assert_awaited_with(CONFIG, (1, 12), "Hello")
            message.content = "<@!99> question"
            await bot.on_message(message)
            answer.assert_awaited_with(CONFIG, (1, 12), "question")
            message.guild = None
            message.content = "DM text"
            await bot.on_message(message)
            answer.assert_awaited_with(CONFIG, (None, 12), "DM text")
            answer.reset_mock()
            message.content = "!ping"
            with patch.object(bot, "process_commands", new=AsyncMock()) as commands:
                await bot.on_message(message)
                commands.assert_awaited_once_with(message)
            answer.assert_not_awaited()
            await bot.get_command("ping").callback(SimpleNamespace(channel=channel))
            self.assertIn("Pong", channel.send.call_args.args[0])
        self.assertTrue(bot.intents.message_content)
        await bot.close()

    async def test_reply_chunks_disable_mentions_and_handle_discord_failure(self):
        channel = SimpleNamespace(send=AsyncMock())
        await bridge.send_reply(channel, "a" * 4001)
        self.assertEqual(channel.send.await_count, 3)
        for call in channel.send.call_args_list:
            self.assertFalse(call.kwargs["allowed_mentions"].everyone)
            self.assertFalse(call.kwargs["allowed_mentions"].users)
        channel.send.side_effect = OSError("SECRET")
        with patch("builtins.print") as output:
            await bridge.send_reply(channel, "hello")
            self.assertNotIn("SECRET", str(output.call_args))


class DiscordDownloadAndConversationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="bridge-owner")
        self.owner.profile.plan = "pro"
        self.owner.profile.save(update_fields=["plan"])
        self.bot = Bot.objects.create(owner=self.owner, name="Bridge")
        self.client.force_login(self.owner)
        self.url = reverse("bots:discord-download", args=[self.bot.pk])

    def test_download_configuration_and_executable_sources(self):
        for domain in ("example.test", "https://example.test/"):
            with patch.dict(os.environ, {"DEFAULT_DOMAIN": domain}):
                response = self.client.post(self.url, {"discord_token": "test-discord"})
            self.assertEqual(response.status_code, 200)
            self.assertIn("no-store", response["Cache-Control"])
            contents = b"".join(response.streaming_content)
            response.close()
            with zipfile.ZipFile(io.BytesIO(contents)) as archive:
                self.assertEqual(set(archive.namelist()), {"discord_bridge/" + name for name in (
                "bridge.py", "backend_url.py", "requirements.txt", "README.txt", "Setup_Guide.pdf", "Commands_Guide.pdf", ".env")})
                env = dict(line.split("=", 1) for line in archive.read("discord_bridge/.env").decode().splitlines())
                self.assertEqual(env["DJANGO_BACKEND"], "https://example.test")
                self.assertEqual(env["DJANGO_BOT_ID"], str(self.bot.pk))
                self.assertTrue(env["DJANGO_API_TOKEN"].startswith("dsc_"))
                for name in ("bridge.py", "backend_url.py"):
                    compile(archive.read("discord_bridge/" + name), name, "exec")

    def test_invalid_download_domain_does_not_issue_credential(self):
        for domain in ("http://example.test", "https://user:secret@example.test", "example.test\nKEY=x"):
            with patch.dict(os.environ, {"DEFAULT_DOMAIN": domain}):
                self.assertEqual(self.client.post(self.url, {"discord_token": "test-discord"}).status_code, 400)
        self.assertFalse(DiscordIntegration.objects.exists())

    def test_download_requires_pro_and_ownership(self):
        other = User.objects.create_user(username="other-download")
        other_bot = Bot.objects.create(owner=other, name="Other")
        self.assertEqual(self.client.post(reverse("bots:discord-download", args=[other_bot.pk]),
                                         {"discord_token": "test-discord"}).status_code, 404)
        self.owner.profile.plan = "free"
        self.owner.profile.save(update_fields=["plan"])
        self.assertEqual(self.client.post(self.url, {"discord_token": "test-discord"}).status_code, 403)
        self.assertFalse(DiscordIntegration.objects.exists())

    def test_first_discord_messages_create_distinct_conversations_and_can_continue(self):
        private = Conversation.objects.create(user=self.owner, bot=self.bot)
        _, secret = issue_discord_integration(self.owner, self.bot)
        client = APIClient()
        url = reverse("bots:discord-api-bot-chat", args=[self.bot.pk])
        def fake_ai(*, user, bot, message, conversation):
            resolved = _resolve_conversation(user, bot, conversation)
            return {"response": "ok", "conversation_id": str(resolved.public_id)}
        with patch("ai_assistant.bots.api_views.process_bot_message", side_effect=fake_ai):
            first = client.post(url, {"message": "one"}, format="json", HTTP_AUTHORIZATION="Discord " + secret)
            second = client.post(url, {"message": "two"}, format="json", HTTP_AUTHORIZATION="Discord " + secret)
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            ids = {str(private.public_id), first.data["conversation_id"], second.data["conversation_id"]}
            self.assertEqual(len(ids), 3)
            continued = client.post(url, {"message": "again", "conversation_id": first.data["conversation_id"]},
                                    format="json", HTTP_AUTHORIZATION="Discord " + secret)
            self.assertEqual(continued.data["conversation_id"], first.data["conversation_id"])

    def test_normal_chat_keeps_existing_conversation_resolution(self):
        token = Token.objects.create(user=self.owner)
        self.owner.profile.plan = "free"
        self.owner.profile.save(update_fields=["plan"])
        client = APIClient()
        with patch("ai_assistant.bots.api_views.process_bot_message", return_value={"response": "ok"}) as ai:
            response = client.post(reverse("bots:api-bot-chat", args=[self.bot.pk]), {"message": "hello"},
                                   format="json", HTTP_AUTHORIZATION="Token " + token.key)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(ai.call_args.kwargs["conversation"])
        self.assertFalse(Conversation.objects.exists())
