import inspect

import httpx
import pytest

from apiroute import Client, Query, Retries, Section, UnexpectedResponse, route

pytestmark = pytest.mark.anyio


class Api(Client):
    base_url = "https://x.test"
    headers = {"Authorization": lambda self: f"Bearer {self.token}"}
    retries = Retries(attempts=3, sleep=0)
    token = "t"
    org: str = "acme"

    @route("/users/{username}")
    def get_user(self, username: str) -> dict:
        """Fetches one user."""

    get_repos = route("/orgs/{org}/repos", query={"page": "{page}"})

    @route("/things", body={"name": "{name}", "draft": True})
    def create_thing(self, name: str): ...

    class issues(Section):
        inherit = ("headers",)

        @route("/issues")
        def list(self, state: Query = None): ...


@pytest.fixture
def api(transport, async_transport):
    return Api(transport=transport, async_transport=async_transport)


async def test_aio_route_returns_parsed_json(api, recorder):
    recorder.respond(httpx.Response(200, json={"login": "octocat"}))
    assert await api.aio.get_user("octocat") == {"login": "octocat"}
    assert str(recorder.last.url) == "https://x.test/users/octocat"
    assert recorder.last.headers["Authorization"] == "Bearer t"
    assert api.last_response.status_code == 200


async def test_aio_methods_are_coroutine_functions_with_the_same_signature(api):
    assert inspect.iscoroutinefunction(api.aio.get_user)
    assert inspect.signature(api.aio.get_user) == inspect.signature(api.get_user)
    assert api.aio.get_user.__doc__ == "Fetches one user."


async def test_generated_routes_and_from_client(api, recorder):
    await api.aio.get_repos(page=2)
    assert str(recorder.last.url) == "https://x.test/orgs/acme/repos?page=2"


async def test_sections_through_aio(api, recorder):
    await api.aio.issues.list(state="open")
    assert str(recorder.last.url) == "https://x.test/issues?state=open"
    assert recorder.last.headers["Authorization"] == "Bearer t"


async def test_with_options_in_either_order(api, recorder):
    await api.aio.with_options(body={"draft": None}).create_thing("x")
    assert recorder.last_json() == {"name": "x"}
    await api.with_options(headers={"X-A": "1"}).aio.create_thing("y")
    assert recorder.last.headers["X-A"] == "1"


async def test_retries_network_errors_without_blocking(api, recorder):
    recorder.respond(httpx.ConnectError("refused"), httpx.Response(200, json={"ok": True}))
    assert await api.aio.get_user("a") == {"ok": True}
    assert len(recorder.requests) == 2


async def test_unexpected_status_raises(api, recorder):
    recorder.respond(httpx.Response(404))
    with pytest.raises(UnexpectedResponse):
        await api.aio.get_user("missing")


async def test_sync_calls_still_use_the_sync_transport(api, recorder):
    api.get_user("a")
    await api.aio.get_user("b")
    assert [request.url.path for request in recorder.requests] == ["/users/a", "/users/b"]


def test_transport_arguments_are_checked(transport, async_transport):
    with pytest.raises(TypeError, match="async_transport"):
        Api(transport=async_transport)
    with pytest.raises(TypeError, match="pass it as transport"):
        Api(async_transport=transport)
