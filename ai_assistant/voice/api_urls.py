"""U6.3 voice API routes."""

from django.urls import path
from . import api, upload_api, turn_status_api, audio_api
from .mobile_auth import authenticated_voice_view

urlpatterns = [
    path("<uuid:session_id>/turns/<uuid:request_id>/", authenticated_voice_view(turn_status_api.voice_turn_status, ["GET"]), name="voice-turn-status"),
    path("<uuid:session_id>/turns/<uuid:request_id>/audio/", authenticated_voice_view(audio_api.voice_turn_audio, ["GET"]), name="voice-turn-audio"),
    path("<uuid:session_id>/upload/", authenticated_voice_view(upload_api.upload_voice_audio, ["POST"]), name="voice-upload"),
    path("start/", authenticated_voice_view(api.start_voice, ["POST"]), name="voice-start"),
    path("<uuid:session_id>/", authenticated_voice_view(api.voice_status, ["GET"]), name="voice-status"),
    path("<uuid:session_id>/stop/", authenticated_voice_view(api.stop_voice, ["POST"]), name="voice-stop"),
]
