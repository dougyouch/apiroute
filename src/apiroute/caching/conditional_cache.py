import hashlib
import threading
from collections import OrderedDict
from dataclasses import replace

import httpx

from apiroute.caching.cache_entry import CacheEntry
from apiroute.full_url import full_url
from apiroute.request_spec import RequestSpec

# Request headers that make a response one caller's: never shared between their values
_PRIVATE_HEADERS = ("authorization", "cookie")
_CONDITIONAL_HEADERS = ("if-none-match", "if-modified-since")
OK, NOT_MODIFIED = 200, 304


class ConditionalCache:
    """Revalidates GET responses instead of downloading them again. Set one as a client's
    `conditional_cache`:

        class GitHub(Client):
            conditional_cache = ConditionalCache()

    A 200 GET response with an ETag or Last-Modified is kept; the next GET of the same URL
    sends If-None-Match or If-Modified-Since, and a 304 answer returns the kept body as a 200
    (with response.extensions["apiroute_cache"] == "revalidated"). On GitHub, a 304 doesn't
    count against the rate limit.

    Responses are kept per URL and per Authorization and Cookie header, so one caller never
    gets another's, and per the request headers a response's Vary names. Responses with
    Cache-Control: no-store aren't kept, nor streamed responses. It holds up to max_entries
    responses, dropping the least recently used, and is safe to share between threads.
    """

    def __init__(self, max_entries: int = 1024):
        if max_entries < 1:
            raise ValueError("max_entries must be at least 1")
        self._max_entries = max_entries
        self._entries: OrderedDict[tuple[str, str], CacheEntry] = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        return len(self._entries)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def prepare(self, spec: RequestSpec) -> RequestSpec:
        """The request with conditional headers for the response kept for it, if any."""
        if not _is_cacheable(spec):
            return spec
        entry = self._lookup(spec)
        if entry is None:
            return spec
        conditions = {}
        if entry.etag is not None:
            conditions["If-None-Match"] = entry.etag
        if entry.last_modified is not None:
            conditions["If-Modified-Since"] = entry.last_modified
        return replace(spec, headers={**spec.headers, **conditions})

    def resolve(self, spec: RequestSpec, response: httpx.Response) -> httpx.Response:
        """The kept response for a 304, else the response, which is kept if it can be."""
        if not _is_cacheable(spec):
            return response
        if response.status_code == NOT_MODIFIED:
            entry = self._lookup(spec)
            return response if entry is None else entry.response_for(response)
        if response.status_code == OK and _is_storable(response):
            self._store(spec, response)
        return response

    def _lookup(self, spec: RequestSpec) -> CacheEntry | None:
        key = _key(spec)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None or not _matches(entry, spec):
                return None
            self._entries.move_to_end(key)
            return entry

    def _store(self, spec: RequestSpec, response: httpx.Response) -> None:
        names = [name.strip().lower() for name in response.headers.get("vary", "").split(",")]
        vary = tuple((name, _header(spec, name)) for name in names if name)
        entry = CacheEntry.of(response, vary)
        key = _key(spec)
        with self._lock:
            self._entries[key] = entry
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)


def _is_cacheable(spec: RequestSpec) -> bool:
    """A GET the caller didn't make conditional themselves."""
    return spec.method == "GET" and not any(_header(spec, name) for name in _CONDITIONAL_HEADERS)


def _is_storable(response: httpx.Response) -> bool:
    if "no-store" in response.headers.get("cache-control", "").lower():
        return False
    if response.headers.get("vary", "").strip() == "*":
        return False
    return "etag" in response.headers or "last-modified" in response.headers


def _matches(entry: CacheEntry, spec: RequestSpec) -> bool:
    return all(_header(spec, name) == value for name, value in entry.vary)


def _key(spec: RequestSpec) -> tuple[str, str]:
    url = str(full_url(spec))
    private = "\0".join(_header(spec, name) or "" for name in _PRIVATE_HEADERS)
    return url, hashlib.sha256(private.encode()).hexdigest()


def _header(spec: RequestSpec, name: str) -> str | None:
    return next((value for key, value in spec.headers.items() if key.lower() == name), None)
