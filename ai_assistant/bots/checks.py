from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.caches, deploy=True)
def production_cache_check(app_configs, **kwargs):
    if not settings.DEBUG and not settings.CACHES['default']['BACKEND'].startswith('django_redis.'):
        return [Error('Production rate limiting requires REDIS_URL.', id='bots.E001')]
    return []
