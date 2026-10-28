import collections.abc
import typing
from typing import Any

_ITERABLES = {
    collections.abc.Iterator,
    collections.abc.Iterable,
    collections.abc.AsyncIterator,
    collections.abc.AsyncIterable,
    collections.abc.Generator,
    collections.abc.AsyncGenerator,
}


def item_type(annotation: Any) -> Any:
    """X from Iterator[X], Iterable[X], AsyncIterator[X], Generator[X, ...] and the like; None
    for any other annotation."""
    origin = typing.get_origin(annotation)
    args = typing.get_args(annotation)
    return args[0] if origin in _ITERABLES and args else None
