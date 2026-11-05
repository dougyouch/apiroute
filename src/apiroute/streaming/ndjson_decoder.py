import json
from typing import Any

import httpx


class NdjsonDecoder:
    """Turns the lines of a newline-delimited JSON body into values, converted by the route's
    item converter (model=, or X from an Iterator[X] return annotation). Blank lines are
    skipped; a line that isn't JSON raises json.JSONDecodeError."""

    def __init__(self, converter: Any):
        self._converter = converter

    def encoding(self, response: httpx.Response) -> str:
        """JSON text is UTF-8; a leading byte order mark is dropped."""
        return "utf-8-sig"

    def feed(self, line: str) -> list[Any]:
        if not line.strip():
            return []
        return [self._converter.convert(json.loads(line))]

    def end(self) -> list[Any]:
        return []

    def reset(self) -> None:
        """Nothing is held between lines."""
