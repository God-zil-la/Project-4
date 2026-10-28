from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.chat_service import _save_chat_exchange
from ai_assistant.bots.models import Bot, ChatMessage, Conversation


class ChatSavingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="u63_saving_owner"
        )
        cls.bot = Bot.objects.create(
            owner=cls.user,
            name="U63 Saving Test",
        )
        cls.conversation = Conversation.objects.create(
            user=cls.user,
            bot=cls.bot,
        )

    def test_returned_id_belongs_to_saved_assistant_message(self):
        message_id = _save_chat_exchange(
            conversation=self.conversation,
            bot=self.bot,
            user=self.user,
            user_message="Hello",
            assistant_message="Hello from AI",
        )

        messages = list(
            ChatMessage.objects.filter(
                conversation=self.conversation,
            ).order_by("pk")
        )

        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].sender, ChatMessage.SENDER_USER)
        self.assertEqual(messages[0].message, "Hello")
        self.assertEqual(
            messages[1].sender,
            ChatMessage.SENDER_ASSISTANT,
        )
        self.assertEqual(messages[1].message, "Hello from AI")
        self.assertEqual(message_id, messages[1].pk)
        self.assertNotEqual(message_id, messages[0].pk)

    def test_saved_id_matches_correct_conversation(self):
        second = Conversation.objects.create(
            user=self.user,
            bot=self.bot,
        )

        message_id = _save_chat_exchange(
            conversation=second,
            bot=self.bot,
            user=self.user,
            user_message="Voice input",
            assistant_message="Voice response",
        )

        saved = ChatMessage.objects.get(pk=message_id)
        self.assertEqual(saved.conversation_id, second.pk)
        self.assertEqual(saved.user_id, self.user.pk)
        self.assertEqual(saved.bot_id, self.bot.pk)
        self.assertEqual(
            saved.sender,
            ChatMessage.SENDER_ASSISTANT,
        )
        self.assertFalse(
            ChatMessage.objects.filter(
                conversation=self.conversation
            ).exists()
        )
