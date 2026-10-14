"""Native U5 API key management. Credentials are returned only on rotation."""
from django.db import transaction
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_variables
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import UserProfile
from .api_keys import unused_api_key_hash

@method_decorator(never_cache, name="dispatch")
class NativeApiAccessView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"is_pro": request.user.profile.is_pro})

    @sensitive_variables()
    def post(self, request):
        action = request.data.get("action")
        if action not in ("rotate", "revoke"):
            return Response({"detail": "Invalid action."}, status=400)
        with transaction.atomic():
            profile = UserProfile.objects.select_for_update().get(user=request.user)
            if action == "rotate":
                if not profile.is_pro:
                    return Response({"detail": "Pro required."}, status=403)
                secret = profile.generate_api_key()
                result = {"key": secret, "message": "Save this key now. It is shown once."}
            else:
                profile.api_key = unused_api_key_hash()
                profile.save(update_fields=["api_key"])
                result = {"message": "API key revoked."}
        response = Response(result)
        response["Cache-Control"] = "no-store, private"
        response["Pragma"] = "no-cache"
        return response
