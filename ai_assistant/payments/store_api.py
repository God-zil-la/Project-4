"""Authenticated catalog, preflight, verification and status endpoints."""
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from .store_config import PRODUCTS, StoreError, base_plan, configured
from .store_service import identity_for, refresh_subscriptions, start_purchase, status_for, verify_purchase


class StoreThrottle(UserRateThrottle):
    rate = '30/min'


class StoreView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    throttle_classes = [StoreThrottle]

    def handle_exception(self, exc):
        if isinstance(exc, StoreError):
            return Response({'error': str(exc)}, status=exc.status)
        # Fail closed without returning credentials, tokens, or provider responses.
        if not hasattr(exc, 'status_code'):
            return Response({'error': 'Unable to verify store status. Please retry or restore purchases.'}, status=503)
        return super().handle_exception(exc)

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response


class StoreCatalog(StoreView):
    def get(self, request):
        provider = request.query_params.get('provider')
        if provider not in {'apple', 'google'}:
            raise StoreError('Invalid store.', 400)
        profile = request.user.profile
        identity = identity_for(profile)
        return Response({**status_for(profile), 'provider': provider,
            'account_token': str(identity.token), 'available': configured(provider),
            'products': [{'plan': plan, 'product_id': product,
                'base_plan_id': base_plan(plan) if provider == 'google' else None}
                for plan, product in PRODUCTS.items()]})


class StoreIntent(StoreView):
    def post(self, request):
        identity = start_purchase(request.user, request.data.get('provider'), request.data.get('product_id'))
        return Response({'account_token': str(identity.token)})


class StoreVerify(StoreView):
    def post(self, request):
        verified = verify_purchase(request.user, request.data.get('provider'), request.data.get('reference'))
        return Response({**status_for(request.user.profile), 'verified': True,
                         'pending': verified.state == 'pending'})


class StoreStatus(StoreView):
    def get(self, request):
        return Response(status_for(request.user.profile))

    def post(self, request):
        refresh_subscriptions(request.user)
        return Response(status_for(request.user.profile))
