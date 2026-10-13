"""Strict HTTPS origin validation shared by the bridge and ZIP generator."""
import re
from urllib.parse import urlsplit


def normalize_backend_url(value):
    if not isinstance(value, str) or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Backend must be an HTTPS origin.")
    value = value.strip()
    if not value or any(char.isspace() for char in value) or "\\" in value:
        raise ValueError("Backend must be an HTTPS origin.")
    if "://" not in value:
        value = "https://" + value
    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname or ""
        port = parsed.port
        if (parsed.scheme != "https" or parsed.username is not None
                or parsed.password is not None or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment or "?" in value or "#" in value
                or parsed.netloc.endswith(":") or (port is not None and not 1 <= port <= 65535)
                or len(hostname) > 253 or not all(
                    re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                    for label in hostname.split("."))):
            raise ValueError
    except ValueError:
        raise ValueError("Backend must be an HTTPS origin without credentials, path or query.") from None
    return "https://" + hostname + (f":{port}" if port is not None else "")
