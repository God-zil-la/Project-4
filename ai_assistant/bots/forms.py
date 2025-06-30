from django import forms
from .models import Bot
from .models import KnowledgeBase


class KnowledgeBaseForm(forms.ModelForm):
    class Meta:
        model = KnowledgeBase
        fields = ['file']
    
    # Custom validation for file upload (e.g., only allowing .txt and .pdf)
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if file.size > 10 * 1024 * 1024:  # Limit file size to 10MB
                raise forms.ValidationError("File size exceeds the 10MB limit.")
            if not file.name.endswith(('.txt', '.pdf', '.docx')):
                raise forms.ValidationError("Invalid file type. Only .txt, .pdf, and .docx files are allowed.")
        return file


class BotForm(forms.ModelForm):
    class Meta:
        model = Bot
        fields = ['name', 'description', 'personality', 'category']
        widgets = {
            'personality': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe the bot\'s personality...'}),
            'category': forms.Select(attrs={'class': 'category-select'})
        }
    
    # Add custom validation for the bot's name
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if Bot.objects.filter(name=name).exists():
            raise forms.ValidationError("A bot with this name already exists.")
        return name
