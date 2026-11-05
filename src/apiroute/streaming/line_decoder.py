import httpx


class LineDecoder:
    """Yields a text body's lines as they are, without their line breaks."""

    def encoding(self, response: httpx.Response) -> str:
        """The charset the response declares, else UTF-8."""
        return response.charset_encoding or "utf-8"

    def feed(self, line: str) -> list[str]:
        return [line]

    def end(self) -> list[str]:
        return []

    def reset(self) -> None:
        """Nothing is held between lines."""
