"""Server-side access to saved assistant responses for TTS."""

from uuid import UUID

from django.apps import apps

from .authorization import authorize
from .errors import AuthorizationDenied


def get_assistant_message(*, user, assistant_id, conversation_id, message_id):
    """Return trusted saved text, never client-supplied text."""
    authorize(user, assistant_id)

    if type(message_id) is not int or message_id <= 0:
        raise AuthorizationDenied('tts_denied')

    try:
        conversation_uuid = UUID(str(conversation_id))
        message_model = apps.get_model('bots', 'ChatMessage')
        message = message_model.objects.get(
            pk=message_id,
            user_id=user.pk,
            bot_id=assistant_id,
            conversation__public_id=conversation_uuid,
            conversation__user_id=user.pk,
            conversation__bot_id=assistant_id,
            sender='assistant',
        )
    except Exception as exc:
        raise AuthorizationDenied('tts_denied') from exc

    authorize(user, assistant_id)
    return message.message
