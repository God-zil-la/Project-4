# bots/forms.py

from django import forms
from .models import Bot


class BotForm(forms.ModelForm):
    class Meta:
        model = Bot
        fields = ['name', 'description', 'personality', 'category']
        widgets = {
            'personality': forms.Textarea(attrs={'rows': 3}),
            'category': forms.Select()
        }
