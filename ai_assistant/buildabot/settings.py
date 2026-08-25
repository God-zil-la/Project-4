"""
Django settings for the ai_assistant project.

This configuration handles development and production environments,
email setup, OpenAI/Stripe integration, static/media files,
security settings, and REST API permissions.
"""

import os
import ssl
import certifi
from pathlib import Path
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────────────────────
# Base Configuration
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv()  # Load .env variables

print("SENDGRID_API_KEY =", os.environ.get("SENDGRID_API_KEY"))

# Fix SSL context for Python 3.13+ and some libraries
ssl._create_default_https_context = (
    lambda: ssl.create_default_context(cafile=certifi.where())
)

# ─────────────────────────────────────────────────────────────────────────────
# Security Settings
# ─────────────────────────────────────────────────────────────────────────────

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-placeholder")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() in ("true", "1")
DEBUG = False  # Always override here for local dev

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
]

if DEBUG:
    ALLOWED_HOSTS.append('.ngrok-free.app')
else:
    ALLOWED_HOSTS += [
        'ai-assistants.herokuapp.com',
        'ai-assistants-8c06fcfeab86.herokuapp.com',
        'ai-assistants-8c06fcfeab86-6fbe77963620.herokuapp.com',
    ]

CSRF_TRUSTED_ORIGINS = [
    'https://ai-assistants-8c06fcfeab86-6fbe77963620.herokuapp.com',
]
# ─────────────────────────────────────────────────────────────────────────────
# Installed Apps
# ─────────────────────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sites',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',

    # Project apps
    'ai_assistant.dashboard.apps.DashboardConfig',
    'ai_assistant.bots',
    'ai_assistant.payments.apps.PaymentsConfig',
    'ai_assistant.accounts.apps.AccountsConfig',

    # Third-party
    'rest_framework',
    'rest_framework.authtoken',
]

# ─────────────────────────────────────────────────────────────────────────────
# Middleware Stack
# ─────────────────────────────────────────────────────────────────────────────

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # For serving static files in production
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# ─────────────────────────────────────────────────────────────────────────────
# REST Framework Configuration
# ─────────────────────────────────────────────────────────────────────────────

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# URL & WSGI Configuration
# ─────────────────────────────────────────────────────────────────────────────

ROOT_URLCONF = 'ai_assistant.buildabot.urls'

WSGI_APPLICATION = 'ai_assistant.buildabot.wsgi.application'

# ─────────────────────────────────────────────────────────────────────────────
# Templates
# ─────────────────────────────────────────────────────────────────────────────

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Custom global templates
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# ─────────────────────────────────────────────────────────────────────────────
# Password Validators
# ─────────────────────────────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ─────────────────────────────────────────────────────────────────────────────
# Internationalization
# ─────────────────────────────────────────────────────────────────────────────

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ─────────────────────────────────────────────────────────────────────────────
# Static & Media Files
# ─────────────────────────────────────────────────────────────────────────────

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_DIRS = []
if (BASE_DIR / 'static').exists():
    STATICFILES_DIRS.append(BASE_DIR / 'static')

if DEBUG:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
    print('⚠️ DEVELOPMENT: Using StaticFilesStorage (no manifest)')
else:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    print('⚡️ PRODUCTION: Using CompressedManifestStaticFilesStorage')

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ─────────────────────────────────────────────────────────────────────────────
# Security Settings (HTTPS / Cookies)
# ─────────────────────────────────────────────────────────────────────────────

if DEBUG:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
else:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ─────────────────────────────────────────────────────────────────────────────
# Authentication / Login
# ─────────────────────────────────────────────────────────────────────────────

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# ─────────────────────────────────────────────────────────────────────────────
# Email Configuration (SMTP)
# ─────────────────────────────────────────────────────────────────────────────

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'aibotassistants@gmail.com'
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = 'AI Bot Assistants <aibotassistants@gmail.com>'

# ─────────────────────────────────────────────────────────────────────────────
# Third-Party Keys
# ─────────────────────────────────────────────────────────────────────────────

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

# ─────────────────────────────────────────────────────────────────────────────
# Sessions / Cookies
# ─────────────────────────────────────────────────────────────────────────────

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# Miscellaneous Settings
# ─────────────────────────────────────────────────────────────────────────────

SITE_ID = 1
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24 * 7  # 7 days
DEFAULT_DOMAIN = os.getenv("DEFAULT_DOMAIN", "ai-assistants-8c06fcfeab86.herokuapp.com")
DEFAULT_PROTOCOL = os.getenv("DEFAULT_PROTOCOL", "https")

from django.contrib.messages import constants as messages

MESSAGE_TAGS = {
    messages.DEBUG: 'info',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'danger',
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom limit for Free plan (daily token usage)
FREE_PLAN_DAILY_LIMIT = 15
