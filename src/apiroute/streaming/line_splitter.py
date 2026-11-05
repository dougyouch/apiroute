import codecs
import re

_LINE_BREAK = re.compile(r"\r\n|\r|\n")


class LineSplitter:
    """Decodes a body chunk by chunk and splits it into lines at \\n, \\r\\n or \\r, including a
    character or a \\r\\n split across two chunks. Bytes that don't decode become U+FFFD."""

    def __init__(self, encoding: str):
        self._decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
        self._buffer = ""
        self._after_cr = False

    def feed(self, chunk: bytes) -> list[str]:
        return self._split(self._decoder.decode(chunk))

    def finish(self) -> list[str]:
        """The lines left at the end of the body, the last one without a line break included."""
        lines = self._split(self._decoder.decode(b"", final=True))
        if self._buffer:
            lines.append(self._buffer)
            self._buffer = ""
        return lines

    def _split(self, text: str) -> list[str]:
        if not text:
            return []
        if self._after_cr and text[0] == "\n":  # the \n of a \r\n split across chunks
            text = text[1:]
        self._after_cr = text.endswith("\r")
        lines = _LINE_BREAK.split(self._buffer + text)
        self._buffer = lines.pop()
        return lines
