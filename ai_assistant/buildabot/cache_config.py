"""Shared Redis configuration without connecting during application startup."""
from urllib.parse import urlsplit
from django.core.exceptions import ImproperlyConfigured


def build_cache_config(redis_url, *, heroku_kvs=False):
    if heroku_kvs and (not redis_url or urlsplit(redis_url).scheme != "rediss"):
        raise ImproperlyConfigured("Heroku KVS requires a rediss:// TLS URL.")
    if not redis_url:
        return {"default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "ai-assistant-local-cache",
        }}
    parsed = urlsplit(redis_url)
    if parsed.scheme not in {"redis", "rediss"} or not parsed.hostname:
        raise ImproperlyConfigured("REDIS_URL must be a valid redis:// or rediss:// URL.")
    options = {
        "CLIENT_CLASS": "django_redis.client.DefaultClient",
        "SOCKET_CONNECT_TIMEOUT": 5,
        "SOCKET_TIMEOUT": 5,
        "IGNORE_EXCEPTIONS": False,
        "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
    }
    if parsed.scheme == "rediss":
        # URL query parameters can override connection pool TLS settings.
        if parsed.query:
            raise ImproperlyConfigured("REDIS_URL must not contain TLS query overrides.")
        options["CONNECTION_POOL_KWARGS"] = {
            # Heroku KVS uses self-signed certificates; keep this exception local.
            "ssl_cert_reqs": None if heroku_kvs else "required",
            "ssl_check_hostname": not heroku_kvs,
        }
    return {"default": {
        "BACKEND": "django_redis.cache.RedisCache", "LOCATION": redis_url,
        "KEY_PREFIX": "ai-assistant", "OPTIONS": options,
    }}
