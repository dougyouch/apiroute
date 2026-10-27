import logging
from typing import Any

import httpx

from apiroute.graphql.graphql_error import GraphQLError

NOT_FOUND, NOT_SUPPORTED = "not_found", "not_supported"


class PersistedQueryReply(GraphQLError):
    """A server's answer to a hash-only persisted-query request that isn't a result: "not_found"
    (PersistedQueryNotFound: send the document to register it) or "not_supported"
    (PersistedQueryNotSupported, or any request error, such as GitHub's "A query attribute must
    be specified": the server doesn't do persisted queries, so send full documents).

    It's part of the protocol, not a failure, so it's logged at DEBUG; the persisted call
    handles it and callers never see it."""

    log_level = logging.DEBUG

    def __init__(
        self, kind: str, operation: str, errors: list[Any], data: Any, response: httpx.Response
    ):
        self.kind = kind
        super().__init__(operation, errors, data, response)

    @classmethod
    def kind_of(cls, errors: list[Any], has_data: bool) -> str | None:
        """The reply errors are, or None for an error from executing the query (it has data)."""
        if _says(errors, "PERSISTED_QUERY_NOT_FOUND", "PersistedQueryNotFound"):
            return NOT_FOUND
        if _says(errors, "PERSISTED_QUERY_NOT_SUPPORTED", "PersistedQueryNotSupported"):
            return NOT_SUPPORTED
        return None if has_data else NOT_SUPPORTED


def _says(errors: list[Any], code: str, message: str) -> bool:
    for error in errors:
        if not isinstance(error, dict):
            continue
        extensions = error.get("extensions")
        if error.get("message") == message:
            return True
        if isinstance(extensions, dict) and extensions.get("code") == code:
            return True
    return False
