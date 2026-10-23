import json
from typing import Any


def py_str(text: str) -> str:
    """A double-quoted Python string literal (JSON string syntax is valid Python)."""
    return json.dumps(text, ensure_ascii=False)


def py_value(value: Any) -> str:
    """A literal for strings, numbers, booleans, None, lists and dicts, with double quotes."""
    if isinstance(value, str):
        return py_str(value)
    if isinstance(value, dict):
        return "{" + ", ".join(f"{py_value(k)}: {py_value(v)}" for k, v in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(py_value(item) for item in value) + "]"
    return repr(value)
