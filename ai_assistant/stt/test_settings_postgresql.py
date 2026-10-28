"""Only the disposable cluster created by pg_verify.py may be used."""
import os
from .test_settings import *

if os.environ.get('U6_PG_ISOLATED') != 'u61-local-20261016':
    raise RuntimeError('Run through pg_verify.py only')
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.postgresql',
    'HOST': '127.0.0.1', 'PORT': '56461',
    'NAME': 'u61_verification', 'USER': 'u61_test',
    'PASSWORD': os.environ['U6_PG_PASSWORD'],
    'OPTIONS': {'connect_timeout': 5, 'options': '-c statement_timeout=20000 -c lock_timeout=12000'},
    'TEST': {'NAME': 'test_u61_verification'},
}}
