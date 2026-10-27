"""Test helpers for code that uses apiroute clients: a transport that answers from the test,
a scope that installs it for every client, and guards against real network calls.

    with mock_transport() as mock:
        mock.on(operation="getUser").respond(httpx.Response(200, json={"login": "octocat"}))
        assert app.user_name("octocat") == "octocat"
        assert mock.last.params["fields"] == "login"
"""

from apiroute.testing.async_mock_transport import AsyncMockTransport
from apiroute.testing.mock_call import MockCall
from apiroute.testing.mock_route import MockRoute
from apiroute.testing.mock_transport import MockTransport
from apiroute.testing.mock_transport_scope import mock_transport
from apiroute.testing.network_block import NetworkBlocked, block_network
from apiroute.testing.sleep_recording import recorded_sleeps
from apiroute.testing.unmatched_request import UnmatchedRequest

__all__ = [
    "AsyncMockTransport",
    "MockCall",
    "MockRoute",
    "MockTransport",
    "NetworkBlocked",
    "UnmatchedRequest",
    "block_network",
    "mock_transport",
    "recorded_sleeps",
]
