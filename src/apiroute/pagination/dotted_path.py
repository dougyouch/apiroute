from typing import Any


class DottedPath:
    """A path into decoded JSON, such as "response_metadata.next_cursor"; "" is the body."""

    def __init__(self, path: str):
        self.path = path
        self._keys = path.split(".") if path else []

    def read(self, data: Any) -> Any:
        """The value at the path; None when something on the way is missing or not an object."""
        for key in self._keys:
            if not isinstance(data, dict):
                return None
            data = data.get(key)
        return data

    def list_in(self, data: Any) -> list[Any]:
        value = self.read(data)
        if not isinstance(value, list):
            where = f"items {self.path!r}" if self.path else "the body"
            found = "missing" if value is None else f"a {type(value).__name__}, not a list"
            raise ValueError(f"{where} is {found}")
        return value
