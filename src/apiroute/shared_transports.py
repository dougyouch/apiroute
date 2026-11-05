from typing import Any


def shared_transports(client: Any) -> dict[str, Any]:
    """The transports a client sends through, as keyword arguments for another client, so a
    helper client (an auth API an Authenticator calls, say) shares its connection pools, its
    use_transport() registration and, in tests, mock_transport() and MockTransport:

        def fetch_token(self, client):
            reply = AcmeAuth(**shared_transports(client)).refresh({"token": self.refresh_token})
    """
    return {
        "transport": client._http_transport(),
        "async_transport": client._async_http_transport(),
    }
