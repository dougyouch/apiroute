from collections.abc import Callable, Mapping
from typing import Any

from apiroute.text_value import text_value
from apiroute.value_encoder import VALUE_ENCODER

QUERY_FORMATS = ("flat", "nested")


class QueryEncoder:
    """Turns query values into (name, value) pairs.

    "flat" repeats the name for list values (tag=a&tag=b). "nested" uses the bracket style of
    the Ruby gem and Rails (user[name]=ann&tag[]=a), so dicts can be sent too.
    """

    def __init__(
        self, style: str = "flat", encode_value: Callable[[Any], Any] = VALUE_ENCODER.encode
    ):
        if style not in QUERY_FORMATS:
            raise ValueError(f"query_format must be one of {QUERY_FORMATS} or a callable")
        self._style = style
        self._encode_value = encode_value

    def encode(self, data: Mapping[str, Any]) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        add = self._add_nested if self._style == "nested" else self._add_flat
        for name, value in data.items():
            add(pairs, str(name), value)
        return pairs

    def _add_flat(self, pairs: list[tuple[str, str]], name: str, value: Any) -> None:
        if isinstance(value, Mapping):
            raise TypeError(f"query param {name!r} is a dict; set query_format = 'nested'")
        if isinstance(value, (list, tuple)):
            pairs.extend((name, self._text(item)) for item in value)
        else:
            pairs.append((name, self._text(value)))

    def _add_nested(self, pairs: list[tuple[str, str]], name: str, value: Any) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                self._add_nested(pairs, f"{name}[{key}]", item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                self._add_nested(pairs, f"{name}[]", item)
        else:
            pairs.append((name, self._text(value)))

    def _text(self, value: Any) -> str:
        return text_value(value, self._encode_value)
