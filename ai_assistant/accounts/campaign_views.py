from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

from .campaign import redeem


@login_required
@csrf_protect
@require_http_methods(['GET', 'POST'])
def campaign(request):
    context = {}
    if request.method == 'POST':
        try:
            redeem(request.user, request.POST.get('code', ''))
            context['success'] = True
        except ValueError as error:
            context['error'] = str(error)
    request.user.profile.refresh_from_db()
    context['profile'] = request.user.profile
    return render(request, 'accounts/campaign.html', context)
