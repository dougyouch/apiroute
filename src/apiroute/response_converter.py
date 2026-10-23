from typing import Any, Protocol

from apiroute.dataclass_converter import DataclassConverter
from apiroute.model_types import contains, is_model_type, is_pydantic_model
from apiroute.pydantic_converter import PydanticConverter


class ResponseConverter(Protocol):
    def convert(self, data: Any) -> Any: ...


def converter_for(model: Any) -> ResponseConverter | None:
    """The converter for a route's model type, or None when responses stay as parsed JSON.

    A type with a pydantic model in it uses pydantic; one with only dataclasses uses the
    built-in converter, so it behaves the same whether or not pydantic is installed.
    """
    if model is None or not is_model_type(model):
        return None
    if contains(model, is_pydantic_model):
        return PydanticConverter(model)
    return DataclassConverter(model)
