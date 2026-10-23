"""Build API clients declaratively: one @route per endpoint, safe defaults, httpx underneath."""

from apiroute.api_route_error import ApiRouteError
from apiroute.argument_targets import Body, Header, Query
from apiroute.client import Client
from apiroute.from_client import FROM_CLIENT
from apiroute.retries import Retries
from apiroute.route import route
from apiroute.route_definition_error import RouteDefinitionError
from apiroute.section import Section
from apiroute.transport_configuration import close_transports, use_transport
from apiroute.transports import (
    HttpxClientTransport,
    OneShotTransport,
    PooledTransport,
    ThreadLocalTransport,
    Transport,
)
from apiroute.unexpected_response import UnexpectedResponse

__all__ = [
    "Body",
    "Client",
    "FROM_CLIENT",
    "ApiRouteError",
    "Header",
    "HttpxClientTransport",
    "OneShotTransport",
    "PooledTransport",
    "Query",
    "Retries",
    "RouteDefinitionError",
    "Section",
    "ThreadLocalTransport",
    "Transport",
    "UnexpectedResponse",
    "close_transports",
    "route",
    "use_transport",
]
