import os
import ssl
import certifi
from pathlib import Path
from dotenv import load_dotenv
from django.core.mail.backends.smtp import EmailBackend

# Load .env
load_dotenv()

# SSL fix for Python 3.13+
ssl._create_default_https_context = ssl.create_default_context(cafile=certifi.where())

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-placeholder")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() in ("true", "1")

ALLOWED_HOSTS = ['localhost', '127.0.0.1']
if not DEBUG:
    ALLOWED_HOSTS += [
        'ai-assistants.herokuapp.com',
        'ai-assistants-8c06fcfeab86.herokuapp.com',
    ]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sites',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'ai_assistant.dashboard.apps.DashboardConfig',
    'ai_assistant.bots',
    'ai_assistant.payments.apps.PaymentsConfig',
    'ai_assistant.accounts.apps.AccountsConfig',
    'sslserver',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ai_assistant.buildabot.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'ai_assistant.buildabot.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

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

if DEBUG:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
else:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

class PatchedEmailBackend(EmailBackend):
    def __init__(self, *args, **kwargs):
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        super().__init__(*args, **kwargs)

EMAIL_BACKEND = 'ai_assistant.buildabot.settings.PatchedEmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_HOST_USER = 'apikey'
EMAIL_HOST_PASSWORD = os.getenv('SENDGRID_API_KEY')
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = 'aibotassistants@gmail.com'

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")

SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'

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

SITE_ID = 1
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24 * 7
DEFAULT_DOMAIN = os.getenv("DEFAULT_DOMAIN", "ai-assistants-8c06fcfeab86.herokuapp.com")
DEFAULT_PROTOCOL = os.getenv("DEFAULT_PROTOCOL", "https")

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
