import inspect
from typing import Annotated

import httpx
import pytest

from apiroute import Client, Result, RouteDefinitionError, route

seen = []


class Api(Client):
    base_url = "https://x.test"

    @route("/users/{username}")
    def get_login(self, username: str, *, data: Result) -> str:
        return data["login"]

    @route("/users/{username}")
    def get_user(self, username: str, *, user: Annotated[dict, Result()]) -> dict:
        seen.append((self, username, user))

    @route("/raw", returns="response")
    def get_raw(self, *, response: Result) -> int:
        return response.status_code


@pytest.fixture
def api(transport, async_transport):
    return Api(transport=transport, async_transport=async_transport)


def test_the_body_replaces_the_result(api, recorder):
    recorder.respond(httpx.Response(200, json={"login": "octocat"}))
    assert api.get_login("octocat") == "octocat"


def test_returning_none_keeps_the_result_and_the_body_sees_the_arguments(api, recorder):
    seen.clear()
    recorder.respond(httpx.Response(200, json={"id": 1}))
    assert api.get_user("ann") == {"id": 1}
    assert seen == [(api, "ann", {"id": 1})]


def test_the_hook_gets_what_returns_produced(api, recorder):
    recorder.respond(httpx.Response(204))
    assert api.get_raw() == 204


def test_callers_dont_see_the_result_parameter(api):
    assert str(inspect.signature(api.get_login)) == "(username: str) -> str"
    with pytest.raises(TypeError):
        api.get_login("a", data={})


@pytest.mark.anyio
async def test_the_hook_runs_for_async_calls(api, recorder):
    recorder.respond(httpx.Response(200, json={"login": "octocat"}))
    assert await api.aio.get_login("octocat") == "octocat"


def test_result_must_be_keyword_only():
    with pytest.raises(RouteDefinitionError, match="keyword-only"):

        class Bad(Client):
            @route("/x")
            def get_x(self, data: Result): ...


def test_only_one_result_parameter():
    with pytest.raises(RouteDefinitionError, match="both 'a' and 'b'"):

        class Bad(Client):
            @route("/x")
            def get_x(self, *, a: Result, b: Result): ...
