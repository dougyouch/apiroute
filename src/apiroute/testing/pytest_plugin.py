"""pytest fixtures for testing code that uses apiroute clients; pytest loads this plugin
automatically when apiroute is installed. Nothing here is autouse."""

from collections.abc import Iterator

import pytest

from apiroute.testing.mock_transport import MockTransport
from apiroute.testing.mock_transport_scope import mock_transport
from apiroute.testing.network_block import block_network


@pytest.fixture
def apiroute_mock() -> Iterator[MockTransport]:
    """A MockTransport answering every client's requests for the test (see mock_transport())."""
    with mock_transport() as mock:
        yield mock


@pytest.fixture
def apiroute_block_network() -> Iterator[None]:
    """Fails any request that reaches the real network during the test; to apply it to a
    whole suite, use it from an autouse fixture in conftest.py."""
    with block_network():
        yield
