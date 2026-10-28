from pathlib import Path

SECRET_KEY = 'u62-isolated-tests-only'
INSTALLED_APPS = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'rest_framework',
    'rest_framework.authtoken',
    'ai_assistant.tts.apps.TTSConfig',
]
MIDDLEWARE = [
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
]
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
USE_TZ = True
ROOT = Path(__file__).resolve().parents[2]
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3',
    'NAME': str(ROOT / 'runtime/local.sqlite3'),
    # Acquire SQLite's writer lock at transaction entry, avoiding read-to-write
    # upgrade deadlocks under simultaneous requests. PostgreSQL uses row locks.
    'OPTIONS': {'timeout': 10, 'transaction_mode': 'IMMEDIATE'},
    'TEST': {'NAME': str(ROOT / 'runtime/test.sqlite3')}}}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

ROOT_URLCONF = 'ai_assistant.tts.test_urls'
