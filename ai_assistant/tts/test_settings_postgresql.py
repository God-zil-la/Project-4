import os
from .test_settings import *

if os.environ.get('U62_ISOLATED') != 'mock-tests-only':
    raise RuntimeError('Use the isolated verify module')
DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql',
    'HOST': '127.0.0.1', 'PORT': '56462', 'NAME': 'u62_test', 'USER': 'u62_test',
    'PASSWORD': os.environ['U62_PG_PASSWORD'],
    'OPTIONS': {'connect_timeout': 5, 'options': '-c statement_timeout=20000 -c lock_timeout=12000'},
    'TEST': {'NAME': 'test_u62_test'}}}
