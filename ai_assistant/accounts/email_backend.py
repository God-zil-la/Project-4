from django.core.mail.backends.smtp import EmailBackend
import ssl, certifi

class PatchedEmailBackend(EmailBackend):
    def __init__(self, *args, **kwargs):
        self.ssl_context = ssl.create_default_context(cafile=certifi.where())
        super().__init__(*args, **kwargs)
