import functools
from typing import Any


class TypedClient:
    """The base of generated .models views: the same operations as the dict client or section
    they wrap, taking pydantic request models and returning response models.

    Each generated method calls _call, which turns models into plain data, calls the dict
    route and validates what comes back, so typed and dict calls share one HTTP code path.
    Through .aio, the methods return coroutines.
    """

    def __init__(self, parent: Any):
        self._parent = parent
        self._is_async = getattr(parent, "is_async", False)

    @property
    def aio(self) -> "TypedClient":
        return type(self)(self._parent.aio)

    def with_options(self, **options: Any) -> "TypedClient":
        return type(self)(self._parent.with_options(**options))

    def _call(self, route_name: str, response_type: Any, *args: Any, **kwargs: Any) -> Any:
        route = getattr(self._parent, route_name)
        result = route(*map(_plain, args), **{name: _plain(v) for name, v in kwargs.items()})
        if self._is_async:
            return _validated_later(result, response_type)
        return _validated(response_type, result)


async def _validated_later(result: Any, response_type: Any) -> Any:
    return _validated(response_type, await result)


def _validated(response_type: Any, data: Any) -> Any:
    if response_type is None or data is None:
        return data
    return _adapter(response_type).validate_python(data)


@functools.cache
def _adapter(response_type: Any) -> Any:
    # pydantic is needed only by generated .models views, not by apiroute itself
    from pydantic import TypeAdapter

    return TypeAdapter(response_type)


def _plain(value: Any) -> Any:
    """Request models as JSON-ready data, by their wire names, leaving out fields not set."""
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True, exclude_unset=True)
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value
