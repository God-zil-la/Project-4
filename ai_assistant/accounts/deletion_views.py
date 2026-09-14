from django import forms
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from .deletion import DeletionBlocked, delete_account


class DeleteAccountForm(forms.Form):
    password = forms.CharField(
        label='Current password', strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'current-password'}),
    )
    confirm = forms.BooleanField(
        label='I understand that deleting my account and application data is permanent.'
    )


@sensitive_post_parameters('password')
@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def confirm_delete_account(request):
    form = DeleteAccountForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        try:
            delete_account(request.user.pk, password=form.cleaned_data['password'])
        except DeletionBlocked as exc:
            form.add_error(None, str(exc))
        else:
            logout(request)
            messages.success(request, (
                'Your AI Assistant account and application records have been deleted. '
                'Uploaded-file cleanup and provider follow-up are described below.'
            ))
            return redirect('delete_account')
    return render(request, 'accounts/delete_account.html', {'form': form})
