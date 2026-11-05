import datetime
import decimal
import enum
import uuid
from typing import Any


def json_default(value: Any) -> Any:
    """`json.dumps(default=...)` for the standard-library values an API takes as ids, timestamps
    and amounts, so a route called with one sends it as JSON would.

    A UUID is its text, a date, time or datetime is ISO 8601, a Decimal is text (JSON numbers are
    binary floats and would lose precision), and an enum is its value. Anything else is still a
    TypeError, so a value that has no obvious JSON form is never guessed at.
    """
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, enum.Enum):
        return value.value
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
