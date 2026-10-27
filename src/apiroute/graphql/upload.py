import mimetypes
import os
from pathlib import Path
from typing import Any

DEFAULT_TYPE = "application/octet-stream"


class Upload:
    """A file for a GraphQL variable, sent with the multipart request spec:

        client.set_avatar(user_id="u1", file=Upload("avatar.png"))

    source is bytes, a file path (read when the request is built) or a binary file object (read
    once; the bytes are kept, so a second request, such as a persisted-query registration,
    sends them again). filename defaults to the path's or file's name, and content_type to
    the type guessed from the filename."""

    def __init__(self, source: Any, filename: str | None = None, content_type: str | None = None):
        if isinstance(source, str) and not source:
            raise ValueError("Upload needs bytes, a file path or a binary file object")
        self._source = source
        self._read: bytes | None = None
        self.filename = filename or _default_name(source)
        self.content_type = content_type or guess_type(self.filename)

    def part(self) -> tuple[str, bytes, str]:
        """(filename, content, content_type), as a multipart file part."""
        return self.filename, self._content(), self.content_type

    def _content(self) -> bytes:
        source = self._source
        if isinstance(source, bytes):
            return source
        if isinstance(source, (str, os.PathLike)):
            return Path(source).read_bytes()
        if self._read is None:
            self._read = source.read()
        return self._read

    def __repr__(self) -> str:
        return f"Upload({self.filename!r}, {self.content_type!r})"


def guess_type(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or DEFAULT_TYPE


def _default_name(source: Any) -> str:
    if isinstance(source, (str, os.PathLike)):
        return Path(source).name
    name = getattr(source, "name", None)
    return os.path.basename(name) if isinstance(name, str) and name else "upload"
