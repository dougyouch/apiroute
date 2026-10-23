import os
import re

_SEPARATORS = re.compile(r"[/\\]")


def validate_stream_path(path: str | os.PathLike) -> str:
    """Rejects null bytes and any '..' path segment, as the Ruby gem does, so a name built from
    untrusted input can't climb out of the directory the caller chose. Names merely containing
    '..' (report..v2.csv) and absolute paths are fine: the caller decides where files go."""
    text = os.fspath(path)
    if "\0" in text:
        raise ValueError("invalid file path: contains a null byte")
    if ".." in _SEPARATORS.split(text):
        raise ValueError("invalid file path: a '..' segment could escape its directory")
    return os.path.abspath(text)
