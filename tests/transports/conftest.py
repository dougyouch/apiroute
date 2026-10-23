import httpx
import pytest

from apiroute.request_spec import RequestSpec
from apiroute.transports.httpx_client_factory import HttpxClientFactory


def spec(path="/a") -> RequestSpec:
    return RequestSpec("GET", f"https://x.test{path}", {"X-A": "1"}, [("q", "1")], None, 5)


@pytest.fixture
def mock(recorder) -> httpx.MockTransport:
    return httpx.MockTransport(recorder)


@pytest.fixture
def created_clients(monkeypatch) -> list[httpx.Client]:
    """Every httpx.Client a factory builds, in order."""
    clients: list[httpx.Client] = []
    original = HttpxClientFactory.new_client

    def tracking(self):
        client = original(self)
        clients.append(client)
        return client

    monkeypatch.setattr(HttpxClientFactory, "new_client", tracking)
    return clients
