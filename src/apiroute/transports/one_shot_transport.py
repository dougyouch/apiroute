from typing import Any

import httpx

from apiroute.request_spec import RequestSpec
from apiroute.transports.httpx_client_factory import HttpxClientFactory
from apiroute.transports.httpx_client_transport import HttpxClientTransport


class OneShotTransport:
    """A new connection for every request, closed as soon as the response is read.

    Nothing outlives a request, so it suits web servers and forking process managers.
    This is the default, as it is in the Ruby gem.
    """

    def __init__(self, **httpx_options: Any):
        self._factory = HttpxClientFactory(**httpx_options)

    def send(self, spec: RequestSpec) -> httpx.Response:
        with self._factory.new_client() as http_client:
            return HttpxClientTransport(http_client).send(spec)

    def close(self) -> None:
        pass
