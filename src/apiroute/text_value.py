import datetime
import enum
from typing import Any


def text_value(value: Any) -> str:
    """A value as the text a query string, a form or a multipart field carries.

    A bool is `true` or `false`, None is empty, a date, time or datetime is ISO 8601 (`T`, not the
    space `str()` writes), and an enum is its value rather than its name (`red`, not `Color.RED`).
    Everything else is `str(value)`, which is already the wire form for ids and numbers.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    if isinstance(value, enum.Enum):
        return text_value(value.value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    return str(value)
