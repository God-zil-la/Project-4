import secrets
from .models import UserProfile


def generate_unique_api_key():
    while True:
        key = secrets.token_hex(16)
        if not UserProfile.objects.filter(api_key=key).exists():
            return key
