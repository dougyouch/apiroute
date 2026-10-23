from urllib.parse import urlsplit

# Only web URLs, to keep a misconfigured base_url from reaching file:, gopher: and the like
ALLOWED_URL_SCHEMES = ("http", "https")


def validate_base_url(url: str) -> None:
    parts = urlsplit(str(url))
    if parts.scheme.lower() not in ALLOWED_URL_SCHEMES:
        raise ValueError(
            f"invalid base_url scheme {parts.scheme!r} in {url!r}; "
            f"allowed: {', '.join(ALLOWED_URL_SCHEMES)}"
        )
    if not parts.hostname:
        raise ValueError(f"invalid base_url {url!r}: it has no host")
