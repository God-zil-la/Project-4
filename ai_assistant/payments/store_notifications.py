"""Signed Apple V2 and authenticated Google Pub/Sub notifications."""
import base64
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import StoreEvent, StoreIdentity
from .store_config import BUNDLE_ID, StoreError, config, environment
from .store_service import verify_purchase
from . import store_verification as verification


def process(provider, event_id, owner, reference):
    env = environment(provider)
    if not event_id or not owner:
        raise StoreError('Missing notification identity.', 400)
    if StoreEvent.objects.filter(provider=provider, environment=env, event_id=event_id).exists():
        return
    identity = StoreIdentity.objects.select_related('profile__user').filter(token=owner).first()
    if identity is None:
        raise StoreError('Unknown purchase account.', 409)
    if identity.profile_id is not None:
        # Re-fetch latest state, never apply stale notification entitlements.
        verify_purchase(identity.profile.user, provider, reference)
    StoreEvent.objects.get_or_create(provider=provider, environment=env, event_id=event_id)


@csrf_exempt
@require_POST
def apple_notification(request):
    try:
        if len(request.body) > 131072:
            return JsonResponse({'error': 'Payload too large.'}, status=413)
        _, verifier = verification.apple_services()
        notification = verifier.verify_and_decode_notification(json.loads(request.body)['signedPayload'])
        if notification.notificationType.value == 'TEST':
            return JsonResponse({'received': True})
        if not notification.data or not notification.data.signedTransactionInfo:
            raise StoreError('Unsupported notification.', 400)
        tx = verifier.verify_and_decode_signed_transaction(notification.data.signedTransactionInfo)
        process('apple', notification.notificationUUID, tx.appAccountToken, tx.transactionId)
        return JsonResponse({'received': True})
    except StoreError as exc:
        return JsonResponse({'error': str(exc)}, status=exc.status)
    except Exception:
        return JsonResponse({'error': 'Notification could not be verified; retry required.'}, status=503)


def authenticate_google(request):
    from google.auth.transport.requests import Request
    from google.oauth2.id_token import verify_oauth2_token
    audience, email = config('GOOGLE_PUBSUB_AUDIENCE'), config('GOOGLE_PUBSUB_SERVICE_ACCOUNT')
    if not audience or not email:
        raise StoreError()
    header = request.headers.get('Authorization', '')
    if not header.startswith('Bearer '):
        raise StoreError('Authentication required.', 401)
    try:
        claims = verify_oauth2_token(header[7:], Request(), audience=audience)
    except Exception:
        raise StoreError('Invalid notification identity.', 401) from None
    if claims.get('email') != email or claims.get('email_verified') is not True:
        raise StoreError('Invalid notification identity.', 401)


@csrf_exempt
@require_POST
def google_notification(request):
    try:
        authenticate_google(request)
        if len(request.body) > 131072:
            return JsonResponse({'error': 'Payload too large.'}, status=413)
        message = json.loads(request.body)['message']
        data = json.loads(base64.b64decode(message['data'], validate=True))
        if data.get('packageName') != BUNDLE_ID:
            raise StoreError('Package mismatch.', 400)
        if 'testNotification' in data:
            return JsonResponse({'received': True})
        notice = data.get('subscriptionNotification') or data.get('voidedPurchaseNotification')
        if not notice or not notice.get('purchaseToken'):
            raise StoreError('Unsupported notification.', 400)
        verified = verification.verify_google(notice['purchaseToken'])
        process('google', message['messageId'], verified.owner, notice['purchaseToken'])
        return JsonResponse({'received': True})
    except StoreError as exc:
        return JsonResponse({'error': str(exc)}, status=exc.status)
    except Exception:
        return JsonResponse({'error': 'Notification could not be verified; retry required.'}, status=503)
