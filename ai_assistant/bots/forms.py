"""
Forms for creating and managing Bots and uploading Knowledge Base content.
"""

from django import forms
from .models import Bot, KnowledgeBase
from .assistant_validation import (
    NAME_REQUIRED, NAME_TOO_LONG, PERSONALITY_REQUIRED, validate_unique_name,
)
from .customization import TONE_HINT, LENGTH_HINT, ICON_HINT


class KnowledgeBaseForm(forms.ModelForm):
    """
    Form for uploading a knowledge file or manually entering text
    to be used as the bot's custom knowledge base.
    """

    file = forms.FileField(required=False)

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
        Validate uploaded file type.
        """
        file = self.cleaned_data.get("file")

        if file and not file.name.lower().endswith(
            (".txt", ".pdf", ".docx")
        ):
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
        fields = ['name', 'description', 'personality', 'category',
                  'response_tone', 'response_length', 'avatar_icon']
        labels = {'personality': 'Personality & instructions', 'avatar_icon': 'Assistant icon'}
        error_messages = {
            'name': {'required': NAME_REQUIRED, 'max_length': NAME_TOO_LONG},
            'personality': {'required': PERSONALITY_REQUIRED},
        }
        help_texts = {
            'response_tone': TONE_HINT,
            'response_length': LENGTH_HINT,
            'avatar_icon': ICON_HINT,
            'description': (
                'Describe what your assistant helps with and who it is for. '
                'Example: A travel assistant that helps families plan weekend trips.'
            ),
            'personality': (
                'Describe its tone, response style, and how it should help within '
                'the selected category. Example: Be friendly, give concise '
                'suggestions, and ask about the budget before recommending a trip.'
            ),
        }
        widgets = {
            'personality': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': "Describe the bot's personality..."
            }),
            'category': forms.Select(attrs={'class': 'category-select'})
        }

    def __init__(self, *args, **kwargs):
        """
        Capture the owner for the same duplicate check as the API.
        """
        self.user = kwargs.pop('user', None)
        super(BotForm, self).__init__(*args, **kwargs)
        if self.is_bound:
            data = self.data.copy()
            for name in self.Meta.fields:
                if name not in data and (name != 'name' or self.instance.pk):
                    data[name] = (
                        getattr(self.instance, name) if self.instance.pk
                        else Bot._meta.get_field(name).get_default()
                    )
            self.data = data

    def clean_name(self):
        name = self.cleaned_data['name']
        owner = self.user or (self.instance.owner if self.instance.owner_id else None)
        if owner is not None:
            validate_unique_name(name, owner, self.instance)
        return name
