import enum
import io
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from apiroute.text_value import text_value
from apiroute.value_encoder import VALUE_ENCODER


class MultipartEncoder:
    """Encodes a dict as multipart/form-data. Values that are bytes, open files or
    (filename, content[, content_type]) tuples become file parts; the rest become fields, as
    text_value writes them through encode_value. httpx builds the body and its boundary."""

    def __init__(self, encode_value: Callable[[Any], Any] = VALUE_ENCODER.encode):
        self._encode_value = encode_value

    def encode(self, data: Mapping[str, Any]) -> tuple[bytes, str]:
        fields: dict[str, Any] = {}
        files: dict[str, Any] = {}
        for name, value in data.items():
            if value is None:
                continue
            if _is_file(value):
                files[name] = value
            else:
                fields[name] = self._field_value(value)
        request = httpx.Request("POST", "https://multipart.invalid", data=fields, files=files)
        return request.read(), request.headers["Content-Type"]

    def _field_value(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._field_value(item) for item in value]
        if isinstance(value, (str, int, float)) and not isinstance(value, (bool, enum.Enum)):
            return value  # httpx writes these as they are
        return text_value(value, self._encode_value)


def _is_file(value: Any) -> bool:
    return isinstance(value, (bytes, tuple, io.IOBase))
