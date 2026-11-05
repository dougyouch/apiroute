import enum
from collections.abc import Callable
from typing import Any

from apiroute.value_encoder import VALUE_ENCODER


def text_value(value: Any, encode_value: Callable[[Any], Any] = VALUE_ENCODER.encode) -> str:
    """A value as the text a query string, a form or a multipart field carries.

    A bool is `true` or `false`, None is empty, and a str or number is itself. Anything else goes
    through encode_value (Client.encode_value) first, so a date is ISO 8601 (`T`, not the space
    `str()` writes) and an enum its value (`red`, not `Color.RED`). A value encode_value has no
    text for (a TypeError, or a list or dict) is `str(value)`, as it always was.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, (str, int, float)) and not isinstance(value, enum.Enum):
        return str(value)
    try:
        encoded = encode_value(value)
    except TypeError:
        return str(value)
    if encoded is value or isinstance(encoded, (list, dict)):
        return str(value)
    return text_value(encoded, encode_value)
