import json
from collections.abc import Mapping
from typing import Any

from apiroute.response_converter import converter_for


def parse_payload(body: bytes | str | Mapping[str, Any] | list[Any], model: Any = None) -> Any:
    """A webhook's JSON body, parsed (unless it already is), and converted to model when given:
    a pydantic model, a dataclass, or a type holding them (list[Event], Cat | Dog). Generated
    clients' webhooks modules call it with each webhook's payload type. A body that isn't JSON
    raises json.JSONDecodeError; one that doesn't fit the model, pydantic's ValidationError."""
    data = json.loads(body) if isinstance(body, (bytes, bytearray, str)) else body
    converter = converter_for(model)
    return data if converter is None else converter.convert(data)
