from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

import httpx
import pytest
from pydantic import BaseModel

from apiroute import Client, ResponseValidationError, Result, RouteDefinitionError, route


class User(BaseModel):
    id: int
    login: str


@dataclass
class Repo:
    name: str


class Api(Client):
    base_url = "https://x.test"

    @route("/users/{username}")
    def get_user(self, username: str) -> User: ...

    @route("/users/{username}/repos")
    def get_repos(self, username: str) -> list[Repo]: ...

    @route("/raw")
    def get_raw(self) -> dict: ...

    @route("/users/{username}")
    def get_login(self, username: str, *, user: Annotated[User, Result()]) -> str:
        return user.login

    @route("/teams/{id}")
    def get_team(self, id: int) -> Team: ...  # defined below this class

    list_users = route("/users", model=list[User])


@dataclass
class Team:
    slug: str


@pytest.fixture
def api(transport, async_transport):
    return Api(transport=transport, async_transport=async_transport)


def test_pydantic_return_annotation(api, recorder):
    recorder.respond(httpx.Response(200, json={"id": "7", "login": "ann", "extra": 1}))
    assert api.get_user("ann") == User(id=7, login="ann")


def test_dataclass_list_return_annotation(api, recorder):
    recorder.respond(httpx.Response(200, json=[{"name": "a"}, {"name": "b"}]))
    assert api.get_repos("ann") == [Repo("a"), Repo("b")]


def test_plain_annotations_are_left_as_json(api, recorder):
    recorder.respond(httpx.Response(200, json={"a": 1}))
    assert api.get_raw() == {"a": 1}


def test_a_result_hook_gets_the_converted_value(api, recorder):
    recorder.respond(httpx.Response(200, json={"id": 1, "login": "ann"}))
    assert api.get_login("ann") == "ann"


def test_types_defined_after_the_class_are_resolved_on_first_use(api, recorder):
    recorder.respond(httpx.Response(200, json={"slug": "core"}))
    assert api.get_team(1) == Team("core")


def test_model_option_on_generated_routes(api, recorder):
    recorder.respond(httpx.Response(200, json=[{"id": 1, "login": "a"}]))
    assert api.list_users() == [User(id=1, login="a")]


def test_mismatches_raise_with_the_response(api, recorder):
    recorder.respond(httpx.Response(200, json={"id": "not a number"}))
    with pytest.raises(ResponseValidationError, match="get_user") as raised:
        api.get_user("ann")
    assert raised.value.response.status_code == 200


def test_other_return_modes_skip_conversion(api, recorder):
    recorder.respond(httpx.Response(200, json={"id": 1, "login": "a"}))
    assert isinstance(api.with_options(returns="response").get_user("a"), httpx.Response)


@pytest.mark.anyio
async def test_async_calls_convert_too(api, recorder):
    recorder.respond(httpx.Response(200, json={"id": 1, "login": "a"}))
    assert await api.aio.get_user("a") == User(id=1, login="a")


def test_model_needs_a_json_route():
    with pytest.raises(RouteDefinitionError, match="model= needs a JSON response"):

        class Bad(Client):
            get_x = route("/x", model=User, returns="text")
