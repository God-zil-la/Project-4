"""Isolated local tests: no real credentials, database, email, or Redis."""
import os
from unittest.mock import patch

with patch.dict(os.environ, {
    "DJANGO_DEBUG": "true", "DATABASE_URL": "", "REDIS_URL": "",
    "SENDGRID_API_KEY": "", "STRIPE_SECRET_KEY": "sk_test_placeholder",
    "OPENAI_API_KEY": "test-placeholder",
    "DJANGO_SECRET_KEY": "test-only-secret-key-never-use-in-production",
}), patch("dotenv.load_dotenv"):
    from .settings import *  # noqa: F403

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
STRIPE_WEBHOOK_SECRET = "whsec_local_test_only"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
SECURE_SSL_REDIRECT = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
