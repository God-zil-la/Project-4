"""Isolated URL configuration for U6.2 API tests only."""
from django.urls import path

from .api_views import SavedResponseTTSAPIView

urlpatterns = [
    path("tts/", SavedResponseTTSAPIView.as_view(), name="u62-test-tts"),
]
