import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlencode

from apiroute.multipart_encoder import MultipartEncoder
from apiroute.query_encoder import QueryEncoder
from apiroute.value_encoder import VALUE_ENCODER

BODY_FORMATS = ("json", "form", "multipart")


class BodyEncoder:
    """Serializes a route's body data according to its body_format (the route's, else the
    class's). Values JSON can't hold go through encode_value (Client.encode_value)."""

    def __init__(self, body_format: Any, encode_value: Callable[[Any], Any] = VALUE_ENCODER.encode):
        self._format = body_format
        self._encode_value = encode_value

    def encode(self, client: Any, data: Any) -> tuple[bytes | str, str | None]:
        """Returns the content and the Content-Type it implies (None when it implies none)."""
        if isinstance(data, (str, bytes)):
            return data, None
        if callable(self._format):
            encoded = self._format(client, data)
            # a format may name its Content-Type: SOAP envelopes are text/xml or soap+xml
            return encoded if isinstance(encoded, tuple) else (encoded, None)
        if self._format == "form":
            pairs = QueryEncoder("nested", self._encode_value).encode(data)
            return urlencode(pairs), "application/x-www-form-urlencoded"
        if self._format == "multipart":
            return MultipartEncoder(self._encode_value).encode(data)
        return json.dumps(data, default=self._encode_value).encode(), "application/json"
