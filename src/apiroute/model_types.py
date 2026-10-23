import dataclasses
import sys
import types
from typing import Annotated, Any, Union, get_args, get_origin

_UNION_TYPES = (Union, types.UnionType)


def strip_annotated(tp: Any) -> Any:
    return get_args(tp)[0] if get_origin(tp) is Annotated else tp


def is_union(tp: Any) -> bool:
    return get_origin(tp) in _UNION_TYPES


def is_class(tp: Any) -> bool:
    """A real class. On Python 3.10, isinstance(list[int], type) is True, so generic aliases
    are ruled out by their origin."""
    return isinstance(tp, type) and get_origin(tp) is None


def is_dataclass_type(tp: Any) -> bool:
    return is_class(tp) and dataclasses.is_dataclass(tp)


def is_pydantic_model(tp: Any) -> bool:
    """True for a pydantic BaseModel subclass. pydantic is only looked at when something has
    already imported it, which any program defining such a model has."""
    pydantic = sys.modules.get("pydantic")
    return pydantic is not None and is_class(tp) and issubclass(tp, pydantic.BaseModel)


def contains(tp: Any, predicate) -> bool:
    """Whether tp, or any type inside it (list[...], dict[..., ...], unions), matches."""
    tp = strip_annotated(tp)
    return predicate(tp) or any(contains(arg, predicate) for arg in get_args(tp))


def is_model_type(tp: Any) -> bool:
    """Whether a response should be converted to tp: it holds a dataclass or pydantic model.
    Plain dict, list, str or Any responses are returned as parsed."""
    return contains(tp, lambda t: is_dataclass_type(t) or is_pydantic_model(t))
