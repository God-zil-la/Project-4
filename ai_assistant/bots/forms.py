"""
Forms for creating and managing Bots and uploading Knowledge Base content.
"""

from django import forms
from .models import Bot, KnowledgeBase


class KnowledgeBaseForm(forms.ModelForm):
    """
    Form for uploading a knowledge file or manually entering text
    to be used as the bot's custom knowledge base.
    """

    manual_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 5,
            'placeholder': 'Or paste your text here...'
        }),
        required=False,
        label='Manual Text (optional)'
    )

    class Meta:
        model = KnowledgeBase
        fields = ['file']

    def clean(self):
        """
        Ensure that either a file or manual text is provided.
        """
        cleaned_data = super().clean()
        file = cleaned_data.get('file')
        manual_text = cleaned_data.get('manual_text')

        if not file and not manual_text:
            raise forms.ValidationError(
                "Please either upload a file or paste text."
            )
        return cleaned_data

    def clean_file(self):
        """
        Validate uploaded file type and size (max 10MB).
        Only allows .txt, .pdf, and .docx files.
        """
        file = self.cleaned_data.get('file')
        if file:
            if file.size > 10 * 1024 * 1024:
                raise forms.ValidationError(
                    "File size exceeds the 10MB limit."
                )
            if not file.name.endswith(('.txt', '.pdf', '.docx')):
                raise forms.ValidationError(
                    "Invalid file type. Only .txt, .pdf, and .docx files are allowed."
                )
        return file


class BotForm(forms.ModelForm):
    """
    Form for creating or editing a Bot instance.
    """

    class Meta:
        model = Bot
        fields = ['name', 'description', 'personality', 'category']
        widgets = {
            'personality': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': "Describe the bot's personality..."
            }),
            'category': forms.Select(attrs={'class': 'category-select'})
        }

    def __init__(self, *args, **kwargs):
        """
        Optionally capture the user when the form is instantiated,
        for later validation or filtering (not used here directly).
        """
        self.user = kwargs.pop('user', None)
        super(BotForm, self).__init__(*args, **kwargs)
