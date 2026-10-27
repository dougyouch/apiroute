import functools
import weakref
from collections.abc import Callable
from typing import Any

from apiroute.graphql.persisted_query_reply import NOT_FOUND, PersistedQueryReply


class GraphQLPersistedCall:
    """Automatic persisted queries over three bound forms of one route: hash-only first; on
    PersistedQueryNotFound, once more with the document to register it; on
    PersistedQueryNotSupported (or a request error from a server that doesn't know the
    protocol), the full document, and only that from then on for this route on this client
    (`unsupported` holds such clients weakly). The hash-only form's decoder raises those
    replies as PersistedQueryReply; any other error propagates."""

    def __init__(
        self,
        hashed: Callable,
        register: Callable,
        full: Callable,
        unsupported: weakref.WeakSet,
        client: Any,
    ):
        self._hashed = hashed
        self._register = register
        self._full = full
        self._unsupported = unsupported
        self._client = client

    def bound(self, is_async: bool) -> Callable:
        """A function with the route's name and signature that runs the protocol."""
        if is_async:

            async def call(*args: Any, **kwargs: Any) -> Any:
                return await self._async_call(*args, **kwargs)

        else:

            def call(*args: Any, **kwargs: Any) -> Any:
                return self._call(*args, **kwargs)

        functools.update_wrapper(call, self._full)
        call.__signature__ = self._full.__signature__
        return call

    def _call(self, *args: Any, **kwargs: Any) -> Any:
        if self._client in self._unsupported:
            return self._full(*args, **kwargs)
        try:
            return self._hashed(*args, **kwargs)
        except PersistedQueryReply as reply:
            return self._fallback(reply)(*args, **kwargs)

    async def _async_call(self, *args: Any, **kwargs: Any) -> Any:
        if self._client in self._unsupported:
            return await self._full(*args, **kwargs)
        try:
            return await self._hashed(*args, **kwargs)
        except PersistedQueryReply as reply:
            return await self._fallback(reply)(*args, **kwargs)

    def _fallback(self, reply: PersistedQueryReply) -> Callable:
        """What to call after a hash-only request got reply."""
        if reply.kind == NOT_FOUND:
            return self._register
        self._unsupported.add(self._client)
        return self._full
