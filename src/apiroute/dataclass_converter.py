import dataclasses
from typing import Any, get_args, get_origin, get_type_hints

from apiroute.model_types import is_dataclass_type, is_union, strip_annotated


class DataclassConverter:
    """Builds dataclasses (inside lists, dicts and unions too) from parsed JSON, without pydantic.

    Keys the dataclass doesn't declare are ignored, since APIs add fields over time; a
    missing required field raises TypeError. Values aren't type-checked beyond that.
    """

    def __init__(self, model: Any):
        self._model = model

    def convert(self, data: Any) -> Any:
        return self._convert(self._model, data)

    def _convert(self, tp: Any, data: Any) -> Any:
        tp = strip_annotated(tp)
        if is_union(tp):
            return self._convert_union(tp, data)
        if is_dataclass_type(tp):
            return self._convert_dataclass(tp, data)
        origin = get_origin(tp)
        if origin in (list, tuple, set, frozenset) and get_args(tp):
            item = get_args(tp)[0]
            return origin(self._convert(item, value) for value in data)
        if origin is dict and get_args(tp):
            value_type = get_args(tp)[1]
            return {key: self._convert(value_type, value) for key, value in data.items()}
        return data

    def _convert_union(self, tp: Any, data: Any) -> Any:
        options = [arg for arg in get_args(tp) if arg is not type(None)]
        if data is None:
            return None
        errors = []
        for option in options:
            try:
                return self._convert(option, data)
            except (TypeError, KeyError, AttributeError) as error:
                errors.append(error)
        raise TypeError(f"no type in {tp} fits the data: {errors}")

    def _convert_dataclass(self, tp: type, data: Any) -> Any:
        if not isinstance(data, dict):
            raise TypeError(f"{tp.__name__} needs an object, got {type(data).__name__}")
        hints = get_type_hints(tp, include_extras=True)
        values = {
            field.name: self._convert(hints[field.name], data[field.name])
            for field in dataclasses.fields(tp)
            if field.init and field.name in data
        }
        return tp(**values)
