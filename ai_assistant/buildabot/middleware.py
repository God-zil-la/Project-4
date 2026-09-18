from django.http import HttpResponsePermanentRedirect


class CanonicalHostMiddleware:
    """
    Redirect the apex production domain to the canonical www host.
    Other hosts, including localhost and Heroku, are left unchanged.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.get_host().split(":")[0].lower() == "myaiassistantapp.se":
            url = f"https://www.myaiassistantapp.se{request.get_full_path()}"
            return HttpResponsePermanentRedirect(url)

        return self.get_response(request)