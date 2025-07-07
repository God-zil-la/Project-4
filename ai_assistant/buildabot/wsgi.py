import os
from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_assistant.buildabot.settings')

application = get_wsgi_application()
application = WhiteNoise(application, root=str(settings.STATIC_ROOT))
