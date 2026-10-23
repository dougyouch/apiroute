import re

HTTP_METHODS = frozenset(
    {
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "HEAD",
        "OPTIONS",
        "TRACE",
        "COPY",
        "LOCK",
        "UNLOCK",
        "MKCOL",
        "MOVE",
        "PROPFIND",
        "PROPPATCH",
    }
)

# The verb must be the whole name or be followed by '_', so create_user is a POST
# but names such as posts or deleted_users stay GET.
_INFERRED_METHODS = (
    (re.compile(r"(?:post|create|add|insert)(?:_|$)", re.IGNORECASE), "POST"),
    (re.compile(r"(?:put|update|modify|change)(?:_|$)", re.IGNORECASE), "PUT"),
    (re.compile(r"patch(?:_|$)", re.IGNORECASE), "PATCH"),
    (re.compile(r"(?:delete|remove|destroy)(?:_|$)", re.IGNORECASE), "DELETE"),
)


def infer_http_method(route_name: str) -> str:
    for pattern, method in _INFERRED_METHODS:
        if pattern.match(route_name):
            return method
    return "GET"


def normalize_http_method(method: str) -> str:
    upper = method.upper()
    if upper not in HTTP_METHODS:
        raise ValueError(f"unknown HTTP method {method!r}")
    return upper
