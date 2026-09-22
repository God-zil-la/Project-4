from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError

from .models import Bot, ChatMessage, Conversation
from .assistant_validation import (
    NAME_REQUIRED, NAME_TOO_LONG, PERSONALITY_REQUIRED,
    save_assistant, validate_unique_name,
)


class AssistantTextField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError("Enter a text value.")
        return super().to_internal_value(data)


class BotSerializer(serializers.ModelSerializer):
    name = AssistantTextField(max_length=100, error_messages={
        "required": NAME_REQUIRED, "blank": NAME_REQUIRED, "max_length": NAME_TOO_LONG,
    })
    description = AssistantTextField(required=False, allow_blank=True)
    personality = AssistantTextField(required=False, error_messages={
        "blank": PERSONALITY_REQUIRED,
    })
    class Meta:
        model = Bot
        fields = [
            "id",
            "name",
            "description",
            "personality",
            "category",
            "response_tone",
            "response_length",
            "avatar_icon",
            "owner",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "owner",
            "created_at",
        ]


    def validate_name(self, value):
        owner = self.context["request"].user
        try:
            validate_unique_name(value, owner, self.instance)
        except DjangoValidationError as error:
            raise serializers.ValidationError(error.messages)
        return value

    def create(self, validated_data):
        return self._save(Bot(**validated_data))

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        return self._save(instance)

    def _save(self, bot):
        try:
            return save_assistant(bot)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"name": error.messages})


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
    bot_avatar_icon = serializers.CharField(source="bot.avatar_icon", read_only=True)
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = [
            "conversation_id",
            "bot_id",
            "bot_name",
            "bot_avatar_icon",
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
