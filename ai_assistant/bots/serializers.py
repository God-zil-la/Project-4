from rest_framework import serializers

from .models import Bot, ChatMessage, Conversation


class BotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bot
        fields = [
            "id",
            "name",
            "description",
            "personality",
            "category",
            "owner",
        ]
        read_only_fields = [
            "id",
            "owner",
        ]


class ChatMessageSerializer(serializers.ModelSerializer):
    """
    Serializer for messages inside a conversation.
    """

    class Meta:
        model = ChatMessage
        fields = [
            "id",
            "sender",
            "message",
            "timestamp",
        ]
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    """
    Serializer for conversation lists and details.
    """

    conversation_id = serializers.UUIDField(
        source="public_id",
        read_only=True,
    )
    bot_id = serializers.IntegerField(
        source="bot.id",
        read_only=True,
    )
    bot_name = serializers.CharField(
        source="bot.name",
        read_only=True,
    )
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "conversation_id",
            "bot_id",
            "bot_name",
            "title",
            "message_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "conversation_id",
            "bot_id",
            "bot_name",
            "message_count",
            "created_at",
            "updated_at",
        ]

    def get_message_count(self, obj):
        return obj.messages.count()


class ConversationDetailSerializer(
    ConversationSerializer
):
    """
    Serializer for a conversation including
    its complete message history.
    """

    messages = ChatMessageSerializer(
        many=True,
        read_only=True,
    )

    class Meta(
        ConversationSerializer.Meta
    ):
        fields = (
            ConversationSerializer.Meta.fields
            + [
                "messages",
            ]
        )