"""Session-only customer API key management; no credentials in GET responses."""
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.debug import sensitive_variables
from django.views.decorators.http import require_http_methods

from .api_keys import unused_api_key_hash
from .models import UserProfile


@login_required
@never_cache
@csrf_protect
@require_http_methods(["GET", "POST"])
@sensitive_variables()
def api_access(request):
    secret = None
    notice = None
    if request.method == "POST":
        action = request.POST.get("action")
        if action not in ("rotate", "revoke"):
            return HttpResponseBadRequest("Unknown API key action.")
        with transaction.atomic():
            profile = UserProfile.objects.select_for_update().get(user=request.user)
            if action == "rotate":
                if not profile.is_pro:
                    return HttpResponseForbidden("API access requires the Pro plan.")
                secret = profile.generate_api_key()
                notice = "Your previous API key has been invalidated. Save the new key now; it is shown only once."
            else:
                profile.api_key = unused_api_key_hash()
                profile.save(update_fields=["api_key"])
                notice = "Customer API access revoked. Discord credentials and your login are unchanged."
    response = render(request, "accounts/api_access.html", {
        "new_api_key": secret, "notice": notice,
        "api_is_pro": request.user.profile.is_pro,
    })
    response["Referrer-Policy"] = "no-referrer"
    return response
