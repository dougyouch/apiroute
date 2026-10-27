import inspect
from typing import Any


def declares(owner: type, name: str) -> bool:
    """Whether a client or section class declares name: as an attribute, method or property,
    or as an annotation (`org: str`), so a {name} placeholder can fall back to it."""
    return hasattr(owner, name) or any(name in _annotations(base) for base in owner.__mro__)


def _annotations(cls: type) -> dict[str, Any]:
    """A class's own annotations; ones that can't be evaluated still count by name."""
    try:
        return inspect.get_annotations(cls)
    except Exception:
        return vars(cls).get("__annotations__", {})
