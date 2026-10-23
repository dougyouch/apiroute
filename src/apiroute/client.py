import asyncio
import time
from dataclasses import replace
from typing import Any
from urllib.parse import quote

import httpx

from apiroute.base_url_validator import validate_base_url
from apiroute.client_config import ClientConfig
from apiroute.request_spec import RequestSpec
from apiroute.router import Router
from apiroute.transport_configuration import ASYNC_TRANSPORTS, TRANSPORTS, is_async_transport
from apiroute.transports.async_transport import AsyncTransport
from apiroute.transports.transport import Transport

# Network failures worth another attempt; other errors (bad URL, TLS) won't fix themselves
RETRYABLE_ERRORS = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)


class Client(Router):
    """Base class for an API client. Configure it with class attributes and @route methods.

    The class describes the API only. How requests are sent is a Transport, chosen for the
    environment with apiroute.use_transport() or, for one instance, the transport and
    async_transport arguments. Async calls go through client.aio.
    """

    last_response: httpx.Response | None = None

    # Class-level defaults, so a subclass that skips super().__init__() still works
    _base_url: str | None = None
    _transport: Transport | None = None
    _async_transport: AsyncTransport | None = None
    _sleep = staticmethod(time.sleep)
    _async_sleep = staticmethod(asyncio.sleep)

    def __init__(
        self,
        *,
        base_url: str | None = None,
        transport: Transport | None = None,
        async_transport: AsyncTransport | None = None,
    ):
        if base_url is not None:
            validate_base_url(base_url)
        if transport is not None and is_async_transport(transport):
            raise TypeError("transport is async; pass it as async_transport")
        if async_transport is not None and not is_async_transport(async_transport):
            raise TypeError("async_transport is not async; pass it as transport")
        self._base_url = base_url
        self._transport = transport
        self._async_transport = async_transport

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Override to retry other errors, e.g. an UnexpectedResponse with status 503."""
        return isinstance(error, RETRYABLE_ERRORS)

    def on_request(self, request: RequestSpec) -> RequestSpec | None:
        """Runs before every attempt, sync or async. Return a changed request, e.g. one with a
        signature header added through dataclasses.replace, or None to send it as is."""
        return None

    def on_response(self, request: RequestSpec, response: httpx.Response, elapsed: float) -> None:
        """Runs after every response, whatever its status, with the seconds it took; for a
        stream, once the status is in and before the body is read. Use it for metrics or
        logging. Network errors don't reach it; they are logged by the retry policy."""

    def escape_path(self, value: Any) -> str:
        """Every path value is escaped so it stays one segment; override to allow '/'."""
        return quote(str(value), safe="")

    @property
    def _root(self) -> "Client":
        return self

    def _request_config(self) -> ClientConfig:
        config = type(self)._config
        return config if self._base_url is None else replace(config, base_url=self._base_url)

    def _http_transport(self) -> Transport:
        return self._transport or TRANSPORTS.for_class(type(self))

    def _async_http_transport(self) -> AsyncTransport:
        return self._async_transport or ASYNC_TRANSPORTS.for_class(type(self))
