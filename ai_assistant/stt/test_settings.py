"""Standalone test settings. Never imports production configuration or secrets."""
from pathlib import Path

SECRET_KEY = 'u6-isolated-tests-only'
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'ai_assistant.stt.apps.STTConfig']
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.sqlite3',
    'NAME': str(Path(__file__).resolve().parents[2] / 'u6-local.sqlite3'),
    'OPTIONS': {'timeout': 10},
    'TEST': {'NAME': str(Path(__file__).resolve().parents[2] / 'u6-test.sqlite3')},
}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
