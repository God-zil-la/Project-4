"""Public crawler endpoints with an explicit, reviewed page allowlist."""

from xml.etree.ElementTree import Element, SubElement, tostring

from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_safe


PUBLIC_ORIGIN = "https://www.myaiassistantapp.se"
PUBLIC_PAGE_NAMES = ("home", "privacy", "delete_account")


@require_safe
def sitemap(request):
    # Never derive canonical URLs from the request host or user-owned objects.
    root = Element("urlset", xmlns="http://www.sitemaps.org/schemas/sitemap/0.9")
    for name in PUBLIC_PAGE_NAMES:
        entry = SubElement(root, "url")
        SubElement(entry, "loc").text = PUBLIC_ORIGIN + reverse(name)
    return HttpResponse(
        tostring(root, encoding="utf-8", xml_declaration=True),
        content_type="application/xml; charset=utf-8",
    )


@require_safe
def robots(request):
    # Crawler guidance only; private views retain their authentication checks.
    return HttpResponse(
        "User-agent: *\n"
        "Disallow: /accounts/\n"
        "Disallow: /admin/\n"
        "Disallow: /bots/\n"
        "Disallow: /dashboard/\n"
        "Disallow: /payments/\n"
        "Disallow: /media/\n"
        f"\nSitemap: {PUBLIC_ORIGIN}/sitemap.xml\n",
        content_type="text/plain; charset=utf-8",
    )
