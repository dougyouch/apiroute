import logging
from typing import Any

import httpx

from apiroute.graphql.graphql_error import GraphQLError, describe_errors
from apiroute.graphql.persisted_query_reply import PersistedQueryReply
from apiroute.unexpected_response import UnexpectedResponse

logger = logging.getLogger(__name__)

ERROR_MODES = ("raise", "partial")


class GraphQLDecoder:
    """A route decoder that reads a GraphQL response: GraphQLError when it has errors, else
    its data, or the value at data_path ("viewer.repositories") inside it.

    With errors="partial", a response with errors and non-null data returns that data and
    logs the errors instead."""

    def __init__(
        self,
        operation: str,
        data_path: str | None = None,
        errors: str = "raise",
        persisted_replies: bool = False,
    ):
        if errors not in ERROR_MODES:
            raise ValueError(f"errors must be one of {ERROR_MODES}")
        self._operation = operation
        self._data_path = data_path
        self._path = data_path.split(".") if data_path else []
        self._errors = errors
        self._persisted_replies = persisted_replies

    def for_persisted_replies(self) -> "GraphQLDecoder":
        """This decoder for a hash-only persisted-query request: replies that aren't results
        raise PersistedQueryReply, which the persisted call handles."""
        return GraphQLDecoder(self._operation, self._data_path, self._errors, True)

    def __call__(self, response: httpx.Response) -> Any:
        body = self._body(response)
        errors = body.get("errors")
        data = body.get("data")
        if errors:
            self._check_persisted_reply(errors, "data" in body, data, response)
            self._handle_errors(errors, data, response)
        elif not response.is_success:
            raise self._unexpected(response)
        return self._unwrapped(data)

    def _body(self, response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as error:
            raise self._not_graphql(response) from error
        if not isinstance(body, dict) or not ({"data", "errors"} & body.keys()):
            raise self._not_graphql(response)
        return body

    def _check_persisted_reply(
        self, errors: Any, has_data: bool, data: Any, response: httpx.Response
    ) -> None:
        if not self._persisted_replies or not isinstance(errors, list):
            return
        kind = PersistedQueryReply.kind_of(errors, has_data)
        if kind is not None:
            raise PersistedQueryReply(kind, self._operation, errors, data, response)

    def _handle_errors(self, errors: Any, data: Any, response: httpx.Response) -> None:
        if not isinstance(errors, list):
            raise self._not_graphql(response)
        if self._errors == "partial" and data is not None and response.is_success:
            logger.warning("%s returned partial data: %s", self._operation, describe_errors(errors))
            return
        raise GraphQLError(self._operation, errors, data, response)

    def _unwrapped(self, data: Any) -> Any:
        for key in self._path:
            if not isinstance(data, dict):
                return None
            data = data.get(key)
        return data

    def _not_graphql(self, response: httpx.Response) -> UnexpectedResponse:
        return self._unexpected(response, "not a GraphQL response")

    def _unexpected(
        self, response: httpx.Response, reason: str | None = None
    ) -> UnexpectedResponse:
        # A decoder can't reach the client's redact_url, so the message leaves out the query
        # and userinfo, where secrets usually travel; .request keeps the real URL
        url = response.request.url.copy_with(query=None, userinfo=b"")
        return UnexpectedResponse(self._operation, response, reason, shown_url=str(url))
