"""Pro-only publishing and isolated visitor access to the existing chat service."""
import hashlib
import logging
import uuid

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.html import format_html
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, Throttled, ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .chat_service import ChatRateLimitError, ChatUsageLimitError, process_bot_message
from .models import Bot, Conversation

logger = logging.getLogger(__name__)
TOKEN_SALT = 'bots.website-visitor.v1'
TOKEN_MAX_AGE = 60 * 60 * 24 * 30


def has_widget_access(user):
    return user.is_active and getattr(getattr(user, 'profile', None), 'effective_plan', None) == 'pro'


def settings_data(bot):
    allowed = has_widget_access(bot.owner)
    url = (settings.PUBLIC_BASE_URL.rstrip('/') + reverse('bots:public-chat', args=[bot.widget_public_id])) if bot.widget_public_id else ''
    return {
        'allowed': allowed,
        'widget_enabled': bot.widget_enabled,
        'active': allowed and bot.widget_enabled,
        'public_url': url,
        'embed_code': str(format_html('<iframe src="{}" title="AI Assistant chat" width="380" height="600" style="max-width:100%;border:0" loading="lazy" referrerpolicy="no-referrer"></iframe>', url)) if url else '',
    }


def update_settings(user, bot_id, enabled):
    if type(enabled) is not bool:
        raise ValidationError({'widget_enabled': 'Enter true or false.'})
    with transaction.atomic():
        bot = get_object_or_404(Bot.objects.select_for_update(), pk=bot_id, owner=user)
        if enabled and not has_widget_access(user):
            raise PermissionDenied('Website Widget / Public Chatbot requires Pro.')
        bot.widget_enabled = enabled
        if enabled and bot.widget_public_id is None:
            bot.widget_public_id = uuid.uuid4()
        bot.save(update_fields=['widget_enabled', 'widget_public_id'])
    return bot


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def widget_settings(request, bot_id):
    bot = get_object_or_404(Bot, pk=bot_id, owner=request.user)
    error = ''
    status = 200
    if request.method == 'POST':
        try:
            update_settings(request.user, bot_id, request.POST.get('widget_enabled') == 'on')
            return redirect('bots:widget-settings', bot_id=bot_id)
        except PermissionDenied as exc:
            error, status = str(exc.detail), 403
    return render(request, 'bots/widget_settings.html', {'bot': bot, 'widget': settings_data(bot), 'error': error}, status=status)


class NoCacheAPI(APIView):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        response['Referrer-Policy'] = 'no-referrer'
        return response


class WidgetSettingsAPI(NoCacheAPI):
    permission_classes = [IsAuthenticated]

    def get(self, request, bot_id):
        return Response(settings_data(get_object_or_404(Bot, pk=bot_id, owner=request.user)))

    def patch(self, request, bot_id):
        if not isinstance(request.data, dict) or set(request.data) != {'widget_enabled'}:
            raise ValidationError('Send only widget_enabled.')
        return Response(settings_data(update_settings(request.user, bot_id, request.data['widget_enabled'])))


def public_bot(public_id):
    bot = get_object_or_404(Bot.objects.select_related('owner__profile'), widget_public_id=public_id, widget_enabled=True)
    if not has_widget_access(bot.owner):
        raise Http404
    return bot


@require_http_methods(['GET'])
@never_cache
@xframe_options_exempt
def public_chat(request, public_id):
    bot = public_bot(public_id)
    response = render(request, 'bots/public_chat.html', {'bot': bot})
    response['Referrer-Policy'] = 'no-referrer'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    response['Content-Security-Policy'] = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors *"
    return response


def throttle_visitor(request, bot):
    # REMOTE_ADDR is trusted by Django; arbitrary forwarding headers are not.
    digest = hashlib.sha256(request.META.get('REMOTE_ADDR', '').encode()).hexdigest()
    key = f'widget-rate:{bot.pk}:{digest}'
    try:
        if cache.add(key, 1, timeout=60):
            return
        count = cache.incr(key)
    except Exception:
        raise APIException('Chat is temporarily unavailable.') from None
    if count > 30:
        raise Throttled(wait=60)


def token_for(bot, conversation):
    return signing.dumps({'bot': str(bot.widget_public_id), 'owner': bot.owner_id, 'conversation': str(conversation.public_id)}, salt=TOKEN_SALT)


def visitor_conversation(bot, token):
    if not isinstance(token, str) or len(token) > 1024:
        raise NotFound('Visitor session not found. Start a new chat.')
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        if payload['bot'] != str(bot.widget_public_id) or payload['owner'] != bot.owner_id:
            raise ValueError
        return Conversation.objects.get(public_id=payload['conversation'], bot=bot, user=bot.owner, is_widget=True)
    except (signing.BadSignature, KeyError, TypeError, ValueError, Conversation.DoesNotExist):
        raise NotFound('Visitor session not found. Start a new chat.') from None


class PublicAPI(NoCacheAPI):
    authentication_classes = []  # Never inherit the owner's browser login or API token.
    permission_classes = [AllowAny]

    def validated_bot(self, request, public_id, fields):
        bot = public_bot(public_id)
        throttle_visitor(request, bot)
        if not isinstance(request.data, dict) or set(request.data) - set(fields):
            raise ValidationError('Invalid request.')
        return bot


class PublicSessionAPI(PublicAPI):
    def post(self, request, public_id):
        bot = self.validated_bot(request, public_id, ['visitor_token'])
        if 'visitor_token' in request.data:
            conversation = visitor_conversation(bot, request.data['visitor_token'])
        else:
            conversation = Conversation.objects.create(bot=bot, user=bot.owner, is_widget=True)
        return Response({
            'visitor_token': token_for(bot, conversation),
            'messages': list(conversation.messages.order_by('timestamp', 'pk').values('sender', 'message')),
        })


class PublicMessageAPI(PublicAPI):
    def post(self, request, public_id):
        bot = self.validated_bot(request, public_id, ['visitor_token', 'message'])
        message = request.data.get('message')
        if not isinstance(message, str) or not message.strip() or len(message) > 4000:
            raise ValidationError('Enter a message between 1 and 4000 characters.')
        conversation = visitor_conversation(bot, request.data.get('visitor_token'))
        try:
            # Serialize concurrent sends for this visitor using the database lock.
            with transaction.atomic():
                conversation = Conversation.objects.select_for_update().get(pk=conversation.pk)
                error = None
                try:
                    result = process_bot_message(bot.owner, bot, message, conversation=conversation, allow_widget=True)
                except Exception as exc:
                    # Commit usage bookkeeping even on provider failure, as in normal chat.
                    error = exc
            if error is not None:
                raise error
        except ChatRateLimitError as exc:
            raise Throttled(wait=exc.retry_after_seconds) from None
        except ChatUsageLimitError:
            return Response({'error': 'This assistant has reached its usage limit. Please try again later.'}, status=429)
        except Exception:
            logger.exception('Public chat processing failed for bot %s', bot.pk)
            return Response({'error': 'Chat is temporarily unavailable. Please try again later.'}, status=503)
        return Response({'response': result['response']})
