import time
from dataclasses import replace
from typing import Any
from urllib.parse import quote

import httpx

from apiroute.base_url_validator import validate_base_url
from apiroute.client_config import ClientConfig
from apiroute.router import Router
from apiroute.transport_configuration import TRANSPORTS
from apiroute.transports.transport import Transport

# Network failures worth another attempt; other errors (bad URL, TLS) won't fix themselves
RETRYABLE_ERRORS = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)


class Client(Router):
    """Base class for an API client. Configure it with class attributes and @route methods.

    The class describes the API only. How requests are sent is a Transport, chosen for the
    environment with apiroute.use_transport() or, for one instance, the transport argument.
    """

    last_response: httpx.Response | None = None

    # Class-level defaults, so a subclass that skips super().__init__() still works
    _base_url: str | None = None
    _transport: Transport | None = None
    _sleep = staticmethod(time.sleep)

    def __init__(self, *, base_url: str | None = None, transport: Transport | None = None):
        if base_url is not None:
            validate_base_url(base_url)
        self._base_url = base_url
        self._transport = transport

    def should_retry(self, error: Exception, attempt: int) -> bool:
        """Override to retry other errors, e.g. an UnexpectedResponse with status 503."""
        return isinstance(error, RETRYABLE_ERRORS)

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
