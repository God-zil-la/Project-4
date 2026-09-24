"""Disposable U3 browser fixture. In-memory DB and mocked AI; never use live data."""
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch
from wsgiref.simple_server import make_server

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DJANGO_SETTINGS_MODULE'] = 'ai_assistant.buildabot.test_settings'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['OPENAI_API_KEY'] = 'test-only'

import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import Client
from django.core.wsgi import get_wsgi_application
from django.contrib.staticfiles.handlers import StaticFilesHandler
from ai_assistant.bots.models import Bot
from ai_assistant.bots.widget_views import update_settings
import openai

assert settings.DATABASES['default']['NAME'] == ':memory:'
call_command('migrate', verbosity=0)
owner = User.objects.create_user(username='browser-owner')
owner.profile.complimentary_plan = 'pro'
owner.profile.save()
bots = [update_settings(owner, Bot.objects.create(owner=owner, name=name).pk, True) for name in ('Travel guide', 'Second guide')]
client = Client()
client.force_login(owner)
answer = openai.util.convert_to_openai_object({'choices': [{'message': {'content': 'A helpful answer. <img src=x onerror=alert(1)>'}}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}, 'model': 'gpt-4o-mini'})
with patch('ai_assistant.bots.chat_service.openai.ChatCompletion.create', return_value=answer), patch('ai_assistant.bots.chat_service.search_relevant_chunks', return_value={'chunks': [], 'tokens_used': 0, 'input_tokens': 0, 'output_tokens': 0, 'model': None}):
    with make_server('127.0.0.1', 0, StaticFilesHandler(get_wsgi_application())) as server:
        print(json.dumps({'base': f'http://127.0.0.1:{server.server_port}', 'publicIds': [str(bot.widget_public_id) for bot in bots], 'botId': bots[0].pk, 'session': client.cookies['sessionid'].value}), flush=True)
        server.serve_forever()
