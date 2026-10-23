from typing import Any
from urllib.parse import unquote

from apiroute.codegen.openapi.spec_loader import SpecLoader


class RefResolver:
    """Follows $refs: within the spec ("#/components/schemas/Repo") and into other files
    ("common.yaml#/Error", "user.json"), loading each file once."""

    def __init__(self, document: Any, location: str, loader: SpecLoader | None = None):
        self._loader = loader or SpecLoader()
        self._documents: dict[str, Any] = {location: document}
        self._location = location

    def resolve(self, ref: str, base: str | None = None) -> tuple[Any, str, str]:
        """The target of ref, the location of the file holding it, and the ref's own last
        name (used to name models)."""
        base = base or self._location
        file_part, _, pointer = ref.partition("#")
        location = self._loader.join(base, file_part) if file_part else base
        document = self._document(location)
        target = _follow(document, pointer)
        if pointer:
            name = _unescape(pointer.rstrip("/").rsplit("/", 1)[-1])
        else:
            name = file_part.rsplit("/", 1)[-1].rsplit(".", 1)[0]  # user.yaml -> user
        return target, location, name

    def deref(self, value: Any, base: str | None = None) -> Any:
        """value with any chain of $refs at its top followed (not inside it)."""
        seen = set()
        while isinstance(value, dict) and "$ref" in value and value["$ref"] not in seen:
            seen.add(value["$ref"])
            value, base, _ = self.resolve(value["$ref"], base)
        return value

    def _document(self, location: str) -> Any:
        if location not in self._documents:
            self._documents[location] = self._loader.load(location)
        return self._documents[location]


def _follow(document: Any, pointer: str) -> Any:
    value = document
    for part in filter(None, pointer.split("/")):
        key = _unescape(unquote(part))
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def _unescape(part: str) -> str:
    return part.replace("~1", "/").replace("~0", "~")
