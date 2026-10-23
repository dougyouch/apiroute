from typing import Any


def as_list(value: Any) -> Any:
    """XML can't tell a one-item list from a single value, so repeated elements arrive as a
    dict or a string when there is one of them. Generated models validate list fields
    through this (pydantic BeforeValidator) to accept both."""
    if value is None or isinstance(value, list):
        return value
    return [value]
