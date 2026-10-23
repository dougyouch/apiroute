import json
from typing import Any
from urllib.parse import urlencode

from apiroute.query_encoder import QueryEncoder

BODY_FORMATS = ("json", "form")


class BodyEncoder:
    """Serializes a route's body data according to the class's body_format."""

    def __init__(self, body_format: Any):
        self._format = body_format

    def encode(self, client: Any, data: Any) -> tuple[bytes | str, str | None]:
        """Returns the content and the Content-Type it implies (None when it implies none)."""
        if isinstance(data, (str, bytes)):
            return data, None
        if callable(self._format):
            return self._format(client, data), None
        if self._format == "form":
            pairs = QueryEncoder("nested").encode(data)
            return urlencode(pairs), "application/x-www-form-urlencoded"
        return json.dumps(data).encode(), "application/json"
