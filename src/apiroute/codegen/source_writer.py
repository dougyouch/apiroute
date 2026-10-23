import textwrap
from collections.abc import Iterator
from contextlib import contextmanager

_WIDTH = 96


class SourceWriter:
    """Collects lines of generated Python source with indentation."""

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._indent = 0

    def line(self, text: str = "") -> None:
        self._lines.append(f"{'    ' * self._indent}{text}" if text else "")

    def lines(self, *texts: str) -> None:
        for text in texts:
            self.line(text)

    def docstring(self, text: str) -> None:
        text = text.strip().replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
        if not text:
            return
        width = _WIDTH - 4 * self._indent
        if "\n" not in text and len(text) + 6 <= width:
            self.line(f'"""{text}"""')
            return
        # wrapped short enough that the first line still fits with its opening quotes
        text = "\n".join(
            "\n".join(textwrap.wrap(paragraph, width - 6) or [""]) for paragraph in text.split("\n")
        )
        if "\n" not in text:
            self.line(f'"""{text}"""')
            return
        first, rest = text.split("\n", 1)
        self.line(f'"""{first}')
        for part in rest.split("\n"):
            self.line(part.rstrip())
        self.line('"""')

    def comment(self, text: str, max_lines: int) -> None:
        """text as # comment lines, wrapped to the line length and cut to max_lines."""
        width = _WIDTH - 4 * self._indent - 2
        lines = textwrap.wrap(" ".join(text.split()), width)
        for line in lines[:max_lines]:
            self.line(f"# {line}")

    @contextmanager
    def indented(self) -> Iterator[None]:
        self._indent += 1
        try:
            yield
        finally:
            self._indent -= 1

    def text(self) -> str:
        while self._lines and self._lines[-1] == "":
            self._lines.pop()
        return "\n".join(self._lines) + "\n"
