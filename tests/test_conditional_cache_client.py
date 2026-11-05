import gzip
from dataclasses import dataclass

import httpx
import pytest

from apiroute import Client, route
from apiroute.caching import ConditionalCache
from apiroute.testing import MockTransport


@dataclass
class Repo:
    name: str


class GitHub(Client):
    base_url = "https://api.test"
    conditional_cache = ConditionalCache()

    @route("/repos/{name}")
    def get_repo(self, name: str) -> Repo: ...

    get_raw = route("/raw")
    feed = route("/feed", stream="lines")
    create = route("POST", "/repos")


@pytest.fixture(autouse=True)
def fresh_cache():
    GitHub.conditional_cache.clear()


class Server:
    """Answers with an ETag and honours If-None-Match."""

    def __init__(self, body=b'{"name": "apiroute"}', etag='"v1"', encoding=None):
        self.requests = []
        self.body, self.etag, self.encoding = body, etag, encoding

    def __call__(self, request):
        self.requests.append(request)
        if request.headers.get("If-None-Match") == self.etag:
            return httpx.Response(304, headers={"ETag": self.etag})
        headers = {"ETag": self.etag, "Content-Type": "application/json"}
        content = self.body
        if self.encoding == "gzip":
            headers["Content-Encoding"] = "gzip"
            content = gzip.compress(self.body)
        return httpx.Response(200, headers=headers, content=content)


def client(handler):
    from apiroute import AsyncHttpxClientTransport, HttpxClientTransport

    return GitHub(
        transport=HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(handler))),
        async_transport=AsyncHttpxClientTransport(
            httpx.AsyncClient(transport=httpx.MockTransport(handler))
        ),
    )


def test_a_repeated_get_is_revalidated_and_returns_the_kept_body():
    server = Server()
    api = client(server)
    assert api.get_repo("apiroute") == Repo("apiroute")
    assert api.get_repo("apiroute") == Repo("apiroute")
    assert "if-none-match" not in server.requests[0].headers
    assert server.requests[1].headers["If-None-Match"] == '"v1"'


def test_a_changed_resource_is_downloaded_again():
    server = Server()
    api = client(server)
    api.get_repo("apiroute")
    server.etag, server.body = '"v2"', b'{"name": "renamed"}'
    assert api.get_repo("apiroute") == Repo("renamed")
    assert api.get_repo("apiroute") == Repo("renamed")
    assert server.requests[2].headers["If-None-Match"] == '"v2"'


def test_a_compressed_response_is_kept_decoded():
    server = Server(encoding="gzip")
    api = client(server)
    api.get_raw()
    assert api.get_raw() == {"name": "apiroute"}
    assert "content-encoding" not in api.last_response.headers


def test_hooks_see_the_revalidated_response(transport):
    seen = []

    class Hooked(GitHub):
        def on_response(self, request, response, elapsed):
            seen.append((response.status_code, response.extensions.get("apiroute_cache")))

    server = Server()
    from apiroute import HttpxClientTransport

    api = Hooked(
        transport=HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(server)))
    )
    api.get_raw()
    api.get_raw()
    assert seen == [(200, None), (200, "revalidated")]


def test_streams_and_posts_arent_cached():
    server = Server()
    api = client(server)
    list(api.feed())
    list(api.feed())
    api.create(body={})
    api.create(body={})
    assert all("if-none-match" not in r.headers for r in server.requests)


def test_with_the_mock_transport():
    mock = MockTransport()
    mock.on(path="/raw").respond(
        httpx.Response(200, json={"a": 1}, headers={"ETag": '"e"'}),
        httpx.Response(304),
    )
    api = GitHub(transport=mock)
    assert api.get_raw() == api.get_raw() == {"a": 1}
    assert mock.calls[1].request.headers["If-None-Match"] == '"e"'


@pytest.mark.anyio
async def test_async_calls_share_the_cache():
    server = Server()
    api = client(server)
    api.get_raw()
    assert await api.aio.get_raw() == {"name": "apiroute"}
    assert server.requests[1].headers["If-None-Match"] == '"v1"'


def test_a_setting_that_isnt_a_cache_fails():
    with pytest.raises(ValueError, match="conditional_cache must be"):

        class Bad(Client):
            conditional_cache = {}


@pytest.mark.anyio
async def test_async_streams_pass_through():
    server = Server(body=b"a\nb\n")
    api = client(server)
    for _ in range(2):
        lines = await api.aio.feed()
        assert [line async for line in lines] == ["a", "b"]
    assert all("if-none-match" not in r.headers for r in server.requests)
