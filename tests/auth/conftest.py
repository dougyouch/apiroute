import json
from urllib.parse import parse_qsl

import httpx
import pytest

from apiroute import AsyncHttpxClientTransport, HttpxClientTransport

TOKEN_URL = "https://auth.test/oauth/token"


class FakeOAuthServer:
    """An httpx.MockTransport handler playing both an OAuth token endpoint and an API.

    The token endpoint issues token-1, token-2 ... (or queued replies); the API answers 200
    to a request whose bearer token is valid, and 401 otherwise. revoke() makes the API refuse
    the tokens issued so far, as when a token is revoked or expires early.
    """

    def __init__(self):
        self.token_requests: list[httpx.Request] = []
        self.api_requests: list[httpx.Request] = []
        self.token_replies: list = []
        self.expires_in: int | None = 3600
        self.issued = 0
        self.valid: set[str] = set()
        self.refresh_tokens = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if str(request.url).startswith(TOKEN_URL):
            return self._token(request)
        return self._api(request)

    def revoke(self) -> None:
        self.valid.clear()

    def form(self, index: int = -1) -> dict[str, str]:
        return dict(parse_qsl(self.token_requests[index].content.decode()))

    def _token(self, request: httpx.Request) -> httpx.Response:
        self.token_requests.append(request)
        if self.token_replies:
            reply = self.token_replies.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        self.issued += 1
        token = f"token-{self.issued}"
        self.valid.add(token)
        body = {"access_token": token, "token_type": "bearer"}
        if self.expires_in is not None:
            body["expires_in"] = self.expires_in
        if self.refresh_tokens:
            body["refresh_token"] = f"refresh-{self.issued}"
        return httpx.Response(200, json=body)

    def _api(self, request: httpx.Request) -> httpx.Response:
        self.api_requests.append(request)
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme != "Bearer" or token not in self.valid:
            return httpx.Response(401, json={"error": "invalid_token"})
        if request.url.path.endswith("/stream"):
            return httpx.Response(200, content=b"data: ok\n\n")
        return httpx.Response(200, json={"path": request.url.path, "token": token})

    @property
    def api_tokens(self) -> list[str]:
        return [r.headers.get("Authorization", "") for r in self.api_requests]


def json_reply(status: int, body) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(body).encode())


@pytest.fixture
def server() -> FakeOAuthServer:
    return FakeOAuthServer()


@pytest.fixture
def transport(server) -> HttpxClientTransport:
    return HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(server)))


@pytest.fixture
def async_transport(server) -> AsyncHttpxClientTransport:
    return AsyncHttpxClientTransport(httpx.AsyncClient(transport=httpx.MockTransport(server)))
