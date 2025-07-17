from rest_framework import serializers
from .models import Bot


class BotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bot
        fields = [
            'id',
            'name',
            'description',
            'personality',
            'category',
            'owner',
        ]
        read_only_fields = ['id', 'owner']
