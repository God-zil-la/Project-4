import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DJANGO_SETTINGS_MODULE'] = 'ai_assistant.buildabot.test_settings'
import django
django.setup()
from django.template.loader import render_to_string
from ai_assistant.bots.models import Bot
from ai_assistant.bots.forms import KnowledgeBaseForm
html = render_to_string('bots/playground.html', {
    'bot': Bot(id=7, name='Travel guide'), 'knowledge_files': [],
    'knowledge_form': KnowledgeBaseForm(), 'csrf_token': 'a' * 64,
})
Path(sys.argv[1]).write_text(html, encoding='utf-8')
