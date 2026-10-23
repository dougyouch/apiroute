"""Build API clients declaratively: one @route per endpoint, safe defaults, httpx underneath."""

from apiroute.api_route_error import ApiRouteError
from apiroute.argument_targets import Body, Header, Query
from apiroute.client import Client
from apiroute.from_client import FROM_CLIENT
from apiroute.namespace import namespace
from apiroute.request_spec import RequestSpec
from apiroute.response_validation_error import ResponseValidationError
from apiroute.result import Result
from apiroute.retries import Retries
from apiroute.route import route
from apiroute.route_definition_error import RouteDefinitionError
from apiroute.section import Section
from apiroute.transport_configuration import aclose_transports, close_transports, use_transport
from apiroute.transports import (
    AsyncHttpxClientTransport,
    AsyncOneShotTransport,
    AsyncPooledTransport,
    AsyncTransport,
    HttpxClientTransport,
    OneShotTransport,
    PooledTransport,
    ThreadLocalTransport,
    Transport,
)
from apiroute.unexpected_response import UnexpectedResponse

__all__ = [
    "AsyncHttpxClientTransport",
    "AsyncOneShotTransport",
    "AsyncPooledTransport",
    "AsyncTransport",
    "Body",
    "Client",
    "FROM_CLIENT",
    "ApiRouteError",
    "Header",
    "HttpxClientTransport",
    "OneShotTransport",
    "PooledTransport",
    "Query",
    "RequestSpec",
    "ResponseValidationError",
    "Result",
    "Retries",
    "RouteDefinitionError",
    "Section",
    "ThreadLocalTransport",
    "Transport",
    "UnexpectedResponse",
    "aclose_transports",
    "close_transports",
    "namespace",
    "route",
    "use_transport",
]
