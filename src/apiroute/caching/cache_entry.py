from dataclasses import dataclass

import httpx

# Headers that describe the bytes on the wire, not the decoded body the cache keeps
_WIRE_HEADERS = frozenset({"content-encoding", "content-length", "transfer-encoding"})
# Headers a 304 can't update in the stored response (RFC 9111 section 3.2)
_KEPT_ON_UPDATE = _WIRE_HEADERS | {"content-type"}


@dataclass(frozen=True)
class CacheEntry:
    """A stored 200: its decoded body, its headers, and the request header values it varies
    on, which a later request must match to use it."""

    content: bytes
    headers: tuple[tuple[str, str], ...]
    vary: tuple[tuple[str, str | None], ...]

    @classmethod
    def of(cls, response: httpx.Response, vary: tuple[tuple[str, str | None], ...]) -> "CacheEntry":
        headers = tuple(
            (name, value)
            for name, value in response.headers.multi_items()
            if name.lower() not in _WIRE_HEADERS
        )
        return cls(response.content, headers, vary)

    @property
    def etag(self) -> str | None:
        return self._header("etag")

    @property
    def last_modified(self) -> str | None:
        return self._header("last-modified")

    def response_for(self, not_modified: httpx.Response) -> httpx.Response:
        """The stored response as the answer to a 304, with the 304's headers (a new Date,
        rate limit counters) over the stored ones."""
        headers = httpx.Headers(list(self.headers))
        for name, value in not_modified.headers.items():
            if name.lower() not in _KEPT_ON_UPDATE:
                headers[name] = value
        return httpx.Response(
            200,
            headers=headers,
            content=self.content,
            request=not_modified.request,
            extensions={"apiroute_cache": "revalidated"},
        )

    def _header(self, name: str) -> str | None:
        return next((value for key, value in self.headers if key.lower() == name), None)
