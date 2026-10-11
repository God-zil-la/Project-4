"""Validation helpers for U4.3 public widget branding."""

import re

from rest_framework.exceptions import ValidationError


HEX_COLOR = re.compile(r"\A#[0-9a-fA-F]{6}\Z")


def validate_brand_color(value, field_name):
    """Accept an empty color or a six-digit hexadecimal color."""
    if not isinstance(value, str):
        raise ValidationError({field_name: "Enter a color string."})
    if value and not HEX_COLOR.fullmatch(value):
        raise ValidationError({field_name: "Use #RRGGBB format."})
    return value.upper()

MAX_LOGO_BYTES = 512 * 1024
MAX_LOGO_PIXELS = 4_000_000

ALLOWED_LOGO_FORMATS = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
}


def validate_brand_logo(upload):
    """Validate an uploaded logo and return its bytes and verified MIME type."""
    from io import BytesIO

    from PIL import Image, UnidentifiedImageError

    if upload is None or not hasattr(upload, "size") or not hasattr(upload, "read"):
        raise ValidationError({"logo": "Choose a logo file."})

    if upload.size > MAX_LOGO_BYTES:
        raise ValidationError({"logo": "Maximum logo size is 512 KB."})

    data = upload.read(MAX_LOGO_BYTES + 1)

    if not data or len(data) > MAX_LOGO_BYTES:
        raise ValidationError({"logo": "Invalid logo size."})

    try:
        with Image.open(BytesIO(data)) as image:
            if image.format not in ALLOWED_LOGO_FORMATS:
                raise ValidationError({"logo": "Use PNG, JPEG or WebP."})
            if image.width * image.height > MAX_LOGO_PIXELS:
                raise ValidationError({"logo": "Image dimensions are too large."})
            image.verify()

        with Image.open(BytesIO(data)) as image:
            image.load()
            content_type = ALLOWED_LOGO_FORMATS[image.format]

    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError, SyntaxError):
        raise ValidationError({"logo": "Invalid image file."}) from None

    return data, content_type

def get_branding_data(bot, allowed):
    """Return public-safe branding settings for a widget."""
    from .models import WidgetBranding

    branding = WidgetBranding.objects.filter(bot=bot).first()

    if not branding or not allowed:
        return {
            "company_name": "",
            "background_color": "",
            "text_color": "",
            "accent_color": "",
            "hide_powered_by": False,
            "has_logo": False,
        }

    return {
        "company_name": branding.company_name,
        "background_color": branding.background_color,
        "text_color": branding.text_color,
        "accent_color": branding.accent_color,
        "hide_powered_by": branding.hide_powered_by,
        "has_logo": bool(branding.logo_data),
    }

def update_branding_settings(user, bot_id, data):
    """Save validated widget branding for a Pro account."""
    from django.db import transaction
    from django.shortcuts import get_object_or_404
    from rest_framework.exceptions import PermissionDenied

    from .models import Bot, WidgetBranding

    allowed_fields = {
        "company_name",
        "background_color",
        "text_color",
        "accent_color",
        "hide_powered_by",
    }

    if not isinstance(data, dict) or not data or set(data) - allowed_fields:
        raise ValidationError("Invalid branding fields.")

    with transaction.atomic():
        bot = get_object_or_404(
            Bot.objects.select_for_update().select_related("owner__profile"),
            pk=bot_id,
            owner=user,
        )

        if not (
            user.is_active
            and getattr(getattr(user, "profile", None), "effective_plan", None) == "pro"
        ):
            raise PermissionDenied("Custom Branding requires Pro.")

        validated = {}

        for field, value in data.items():
            if field in {"background_color", "text_color", "accent_color"}:
                validated[field] = validate_brand_color(value, field)
            elif field == "company_name":
                if not isinstance(value, str) or len(value.strip()) > 100:
                    raise ValidationError({"company_name": "Maximum 100 characters."})
                validated[field] = value.strip()
            elif field == "hide_powered_by":
                if type(value) is not bool:
                    raise ValidationError({"hide_powered_by": "Enter true or false."})
                validated[field] = value

        branding, _ = WidgetBranding.objects.get_or_create(bot=bot)

        for field, value in validated.items():
            setattr(branding, field, value)

        branding.save(update_fields=list(validated))
        return bot

def update_branding_logo(user, bot_id, upload):
    """Store a validated logo for a Pro widget."""
    from django.db import transaction
    from django.shortcuts import get_object_or_404
    from rest_framework.exceptions import PermissionDenied

    from .models import Bot, WidgetBranding

    data, content_type = validate_brand_logo(upload)

    with transaction.atomic():
        bot = get_object_or_404(
            Bot.objects.select_for_update().select_related("owner__profile"),
            pk=bot_id,
            owner=user,
        )

        if not (
            user.is_active
            and getattr(getattr(user, "profile", None), "effective_plan", None) == "pro"
        ):
            raise PermissionDenied("Custom Branding requires Pro.")

        branding, _ = WidgetBranding.objects.get_or_create(bot=bot)
        branding.logo_data = data
        branding.logo_content_type = content_type
        branding.save(update_fields=["logo_data", "logo_content_type"])

        return bot

def remove_branding_logo(user, bot_id):
    """Remove only the logo from a Pro widget."""
    from django.db import transaction
    from django.shortcuts import get_object_or_404
    from rest_framework.exceptions import PermissionDenied

    from .models import Bot, WidgetBranding

    with transaction.atomic():
        bot = get_object_or_404(
            Bot.objects.select_for_update().select_related("owner__profile"),
            pk=bot_id,
            owner=user,
        )

        if not (
            user.is_active
            and getattr(getattr(user, "profile", None), "effective_plan", None) == "pro"
        ):
            raise PermissionDenied("Custom Branding requires Pro.")

        WidgetBranding.objects.filter(bot=bot).update(
            logo_data=None,
            logo_content_type="",
        )

        return bot

def get_public_branding_logo(bot):
    """Return a verified stored logo without exposing other branding data."""
    from django.http import Http404

    from .models import WidgetBranding

    branding = WidgetBranding.objects.filter(bot=bot).first()

    if not branding or not branding.logo_data:
        raise Http404

    if branding.logo_content_type not in ALLOWED_LOGO_FORMATS.values():
        raise Http404

    data = bytes(branding.logo_data)

    if not data or len(data) > MAX_LOGO_BYTES:
        raise Http404

    return data, branding.logo_content_type

def get_public_branding_css(bot):
    """Generate CSS overrides from validated widget branding colors."""
    from .models import WidgetBranding

    branding = WidgetBranding.objects.filter(bot=bot).first()
    if not branding:
        return ""

    mapping = {
        "background_color": "--bg-color",
        "text_color": "--text-color",
        "accent_color": "--accent-color",
    }

    declarations = []

    for field, css_variable in mapping.items():
        value = getattr(branding, field)
        if value:
            try:
                color = validate_brand_color(value, field)
            except ValidationError:
                continue
            declarations.append(f"    {css_variable}: {color};")

    if not declarations:
        return ""

    rules = "\n".join(declarations)
    return f":root, html.dark {{\n{rules}\n}}\n"
