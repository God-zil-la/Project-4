"""No credentials or prices in source; store prices are loaded on the device."""
from django.conf import settings

PRODUCTS = {
    'premium': 'com.mrhusse.aiassistant.premium.monthly',
    'pro': 'com.mrhusse.aiassistant.pro.monthly',
}
APPLE_GROUP = '22427524'
BUNDLE_ID = 'com.mrhusse.aiassistant'


class StoreError(Exception):
    def __init__(self, message='Store verification is temporarily unavailable.', status=503):
        super().__init__(message)
        self.status = status


def config(name, default=''):
    return getattr(settings, 'STORE_' + name, default)


def environment(provider):
    value = config(provider.upper() + '_ENVIRONMENT')
    if value not in {'production', 'sandbox'}:
        raise StoreError()
    return value


def base_plan(plan):
    # Proposed console values: monthly for each product. Empty until confirmed.
    return config('GOOGLE_' + plan.upper() + '_BASE_PLAN_ID')


def configured(provider):
    names = (['APPLE_ENVIRONMENT', 'APPLE_KEY_ID', 'APPLE_ISSUER_ID',
              'APPLE_PRIVATE_KEY_PATH', 'APPLE_ROOT_CERT_PATHS', 'APPLE_APP_ID']
             if provider == 'apple' else
             ['GOOGLE_ENVIRONMENT', 'GOOGLE_CREDENTIALS_JSON', 'TOKEN_ENCRYPTION_KEY',
              'GOOGLE_PREMIUM_BASE_PLAN_ID', 'GOOGLE_PRO_BASE_PLAN_ID'])
    return all(config(name) for name in names)

