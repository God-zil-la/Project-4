# bots/forms.py

from django import forms
from .models import Bot
from .models import KnowledgeBase

class KnowledgeBaseForm(forms.ModelForm):
    class Meta:
        model = KnowledgeBase
        fields = ['file']



class BotForm(forms.ModelForm):
    class Meta:
        model = Bot
        fields = ['name', 'description', 'personality', 'category']
        widgets = {
            'personality': forms.Textarea(attrs={'rows': 3}),
            'category': forms.Select()
        }
