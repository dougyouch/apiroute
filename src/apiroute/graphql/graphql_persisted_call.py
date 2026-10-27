import functools
import weakref
from collections.abc import Callable
from typing import Any

from apiroute.graphql.graphql_error import GraphQLError

NOT_FOUND = ("PERSISTED_QUERY_NOT_FOUND", "PersistedQueryNotFound")
NOT_SUPPORTED = ("PERSISTED_QUERY_NOT_SUPPORTED", "PersistedQueryNotSupported")


class GraphQLPersistedCall:
    """Automatic persisted queries over three bound forms of one route: hash-only first; on
    PersistedQueryNotFound, once more with the document to register it; on
    PersistedQueryNotSupported, the full document, and only that from then on for this route
    on this client (`unsupported` holds such clients weakly)."""

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
        except GraphQLError as error:
            return self._fallback(error)(*args, **kwargs)

    async def _async_call(self, *args: Any, **kwargs: Any) -> Any:
        if self._client in self._unsupported:
            return await self._full(*args, **kwargs)
        try:
            return await self._hashed(*args, **kwargs)
        except GraphQLError as error:
            return await self._fallback(error)(*args, **kwargs)

    def _fallback(self, error: GraphQLError) -> Callable:
        """What to call after a hash-only request failed with error, or raise it."""
        if _replied(error, NOT_FOUND):
            return self._register
        if _replied(error, NOT_SUPPORTED):
            self._unsupported.add(self._client)
            return self._full
        raise error


def _replied(error: GraphQLError, reply: tuple[str, str]) -> bool:
    """Whether the server's errors are that APQ reply, by extensions.code or message."""
    code, message = reply
    messages = [e.get("message") for e in error.errors if isinstance(e, dict)]
    return code in error.codes or message in messages
