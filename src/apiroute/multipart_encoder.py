import enum
import io
from collections.abc import Mapping
from typing import Any

import httpx

from apiroute.text_value import text_value


class MultipartEncoder:
    """Encodes a dict as multipart/form-data. Values that are bytes, open files or
    (filename, content[, content_type]) tuples become file parts; the rest become fields.
    httpx builds the body and its boundary."""

    def encode(self, data: Mapping[str, Any]) -> tuple[bytes, str]:
        fields: dict[str, Any] = {}
        files: dict[str, Any] = {}
        for name, value in data.items():
            if value is None:
                continue
            if _is_file(value):
                files[name] = value
            else:
                fields[name] = _field_value(value)
        request = httpx.Request("POST", "https://multipart.invalid", data=fields, files=files)
        return request.read(), request.headers["Content-Type"]


def _is_file(value: Any) -> bool:
    return isinstance(value, (bytes, tuple, io.IOBase))


def _field_value(value: Any) -> Any:
    if isinstance(value, list):
        return [_field_value(item) for item in value]
    if isinstance(value, (str, int, float)) and not isinstance(value, (bool, enum.Enum)):
        return value  # httpx writes these as they are
    return text_value(value)
