import io
import os
from typing import Any

from apiroute.graphql.upload import Upload, guess_type


class GraphQLUploads:
    """Finds the files in a call's variables (Upload values and open binary files, at any
    depth in dicts and lists) for the multipart request spec: the variables with each file
    replaced by None, and each distinct file with the variable paths it fills."""

    def __init__(self, variables: dict[str, Any]):
        self._parts: list[tuple[Any, list[str]]] = []
        self._index: dict[int, int] = {}  # id(file) -> its part
        self.variables = {
            name: self._walk(value, f"variables.{name}") for name, value in variables.items()
        }

    def __bool__(self) -> bool:
        return bool(self._parts)

    def map(self) -> dict[str, list[str]]:
        """The spec's map: part name -> the variable paths that file fills."""
        return {str(index): paths for index, (_, paths) in enumerate(self._parts)}

    def files(self) -> dict[str, tuple[str, bytes, str]]:
        """Part name -> (filename, content, content_type)."""
        return {str(index): _part(file) for index, (file, _) in enumerate(self._parts)}

    def _walk(self, value: Any, path: str) -> Any:
        if _is_file(value):
            self._add(value, path)
            return None
        if isinstance(value, dict):
            return {key: self._walk(item, f"{path}.{key}") for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._walk(item, f"{path}.{index}") for index, item in enumerate(value)]
        return value

    def _add(self, file: Any, path: str) -> None:
        index = self._index.get(id(file))
        if index is None:
            self._index[id(file)] = len(self._parts)
            self._parts.append((file, [path]))
        else:
            self._parts[index][1].append(path)


def _is_file(value: Any) -> bool:
    if isinstance(value, io.TextIOBase):
        raise TypeError("a file in a GraphQL variable must be opened in binary mode ('rb')")
    return isinstance(value, (Upload, io.IOBase))


def _part(file: Any) -> tuple[str, bytes, str]:
    if isinstance(file, Upload):
        return file.part()
    name = os.path.basename(getattr(file, "name", "") or "") or "upload"
    return name, _read_in_place(file), guess_type(name)


def _read_in_place(file: Any) -> bytes:
    """A bare file's bytes from where it stands, seeking back when it can, so the same call's
    next request (a persisted-query registration) reads them again."""
    if not file.seekable():
        return file.read()
    start = file.tell()
    content = file.read()
    file.seek(start)
    return content
