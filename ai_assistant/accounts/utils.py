from .api_keys import unused_api_key_hash
from .models import UserProfile


def generate_unique_api_key():
    while True:
        digest = unused_api_key_hash()
        if not UserProfile.objects.filter(api_key=digest).exists():
            return digest
