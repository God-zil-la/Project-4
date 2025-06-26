from django.core.mail.backends.smtp import EmailBackend
import ssl

class PatchedEmailBackend(EmailBackend):
    def __init__(self, *args, **kwargs):
        # ABSOLUTE DEV-ONLY: DISABLE CERT VALIDATION FOR WINDOWS/PYTHON 3.13
        self.ssl_context = ssl._create_unverified_context()
        super().__init__(*args, **kwargs)
