import builtins
import functools
import importlib
import io
import sys
import typing
from typing import Any, TypeVar

T = TypeVar("T", bound="TypedClient")


class TypedClient:
    """The base of generated .models views: the same operations as the dict client or section
    they wrap, taking pydantic request models and returning response models.

    Each generated method calls _call, which turns models into plain data, calls the dict
    route and validates what comes back, so typed and dict calls share one HTTP code path.
    Through .aio, the methods return coroutines.

    A response type may be given as source text ("list[Repository]"). Its names are looked up
    in the models.py next to the generated class, on the method's first call, so a typed
    call imports only the models it returns.
    """

    def __init__(self, parent: Any):
        self._parent = parent
        self._is_async = getattr(parent, "is_async", False)

    @property
    def aio(self) -> Any:
        """The same view, whose methods return coroutines; Any to type checkers, since the
        methods' annotations describe the sync results."""
        return type(self)(self._parent.aio)

    def with_options(self: T, **options: Any) -> T:
        return type(self)(self._parent.with_options(**options))

    def _call(self, route_name: str, response_type: Any, *args: Any, **kwargs: Any) -> Any:
        route = getattr(self._parent, route_name)
        result = route(*map(_plain, args), **{name: _plain(v) for name, v in kwargs.items()})
        if isinstance(response_type, str):
            response_type = _resolved(type(self).__module__, response_type)
        if self._is_async:
            return _validated_later(result, response_type)
        return _validated(response_type, result)

    def _paginate(self, route_name: str, item_type: Any, *args: Any, **kwargs: Any) -> Any:
        """_call for a paginated route: the dict route's items, each validated as item_type
        when iteration reaches it (an async iterator through .aio)."""
        route = getattr(self._parent, route_name)
        items = route(*map(_plain, args), **{name: _plain(v) for name, v in kwargs.items()})
        if isinstance(item_type, str):
            item_type = _resolved(type(self).__module__, item_type)
        if self._is_async:
            return _validated_async_items(items, item_type)
        return _validated_items(items, item_type)


def _validated_items(items: Any, item_type: Any) -> Any:
    for item in items:
        yield _validated(item_type, item)


async def _validated_async_items(items: Any, item_type: Any) -> Any:
    async for item in items:
        yield _validated(item_type, item)


async def _validated_later(result: Any, response_type: Any) -> Any:
    return _validated(response_type, await result)


def _validated(response_type: Any, data: Any) -> Any:
    if response_type is None or data is None:
        return data
    return _adapter(response_type).validate_python(data)


@functools.cache
def _resolved(client_module: str, expression: str) -> Any:
    """expression evaluated with its names taken from the client's sibling models module."""
    package = sys.modules[client_module].__package__
    models = importlib.import_module(".models", package)
    return eval(expression, {"__builtins__": builtins}, _ModelNames(models))  # noqa: S307


class _ModelNames(dict):
    """Names for _resolved: typing's (Any, Literal), else the models module's, imported lazily."""

    def __init__(self, models: Any):
        super().__init__()
        self._models = models

    def __missing__(self, name: str) -> Any:
        if hasattr(typing, name):
            return getattr(typing, name)
        try:
            return getattr(self._models, name)
        except AttributeError:
            raise KeyError(name) from None  # lets eval fall back to builtins such as list


@functools.cache
def _adapter(response_type: Any) -> Any:
    # pydantic is needed only by generated .models views, not by apiroute itself
    from pydantic import TypeAdapter

    return TypeAdapter(response_type)


def _plain(value: Any) -> Any:
    """Request models as JSON-ready data, by their wire names, leaving out fields not set.
    Files (GraphQL Upload values, open files, (name, content, type) tuples, bytes) stay as
    they are, for a multipart request."""
    if hasattr(value, "model_dump"):
        dumped = _with_uploads(value).model_dump(mode="python", by_alias=True, exclude_unset=True)
        return _jsonable(dumped)
    if isinstance(value, tuple):  # kept a tuple: the multipart encoder reads one as a file
        return tuple(_plain(item) for item in value)
    if isinstance(value, list):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    return value


def _with_uploads(model: Any) -> Any:
    """The model, or a copy with its open files wrapped in Upload: pydantic would otherwise
    dump a file in an Any field as the list of its lines, reading it."""
    updates = {}
    for name, item in vars(model).items():
        wrapped = _files_wrapped(item)
        if wrapped is not item:
            updates[name] = wrapped
    return model.model_copy(update=updates) if updates else model


def _files_wrapped(value: Any) -> Any:
    from apiroute.graphql.upload import Upload

    if isinstance(value, io.IOBase):
        return Upload(value)
    if hasattr(value, "model_dump"):
        return _with_uploads(value)
    if isinstance(value, (list, tuple)):
        items = [_files_wrapped(item) for item in value]
        return items if any(a is not b for a, b in zip(items, value, strict=True)) else value
    if isinstance(value, dict):
        items = {key: _files_wrapped(item) for key, item in value.items()}
        return items if any(items[k] is not value[k] for k in value) else value
    return value


def _jsonable(value: Any) -> Any:
    """A model's dumped data with values JSON can't hold (datetimes, enums, UUIDs) converted
    as pydantic's JSON mode would, except files, which a GraphQL body sends as parts."""
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):  # a (name, content, type) file for a multipart body
        return tuple(_jsonable(item) for item in value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool, bytes)) or _is_file(value):
        return value
    from pydantic_core import to_jsonable_python

    return to_jsonable_python(value)


def _is_file(value: Any) -> bool:
    from apiroute.graphql.upload import Upload

    return isinstance(value, (Upload, io.IOBase))
