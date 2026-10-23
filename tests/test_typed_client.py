import httpx
import pytest

pytest.importorskip("pydantic")
from pydantic import BaseModel, Field

from apiroute import Client, TypedClient, route


class NewRepo(BaseModel):
    name: str
    is_private: bool = Field(False, alias="private")
    description: str | None = None


class Repo(BaseModel):
    id: int
    name: str


class Api(Client):
    base_url = "https://x.test"

    @route("/repos")
    def create_repo(self, body): ...

    @route("/repos")
    def list_repos(self): ...


class ApiModels(TypedClient):
    def create_repo(self, body: NewRepo) -> Repo:
        return self._call("create_repo", Repo, body=body)

    def list_repos(self) -> list[Repo]:
        return self._call("list_repos", list[Repo])


@pytest.fixture
def models(transport, async_transport):
    return ApiModels(Api(transport=transport, async_transport=async_transport))


def test_request_models_go_out_by_alias_without_unset_fields(models, recorder):
    recorder.respond(httpx.Response(201, json={"id": 1, "name": "api"}))
    repo = models.create_repo(NewRepo(name="api", private=True))
    assert recorder.last_json() == {"name": "api", "private": True}
    assert repo == Repo(id=1, name="api")


def test_responses_validate_into_generic_types(models, recorder):
    recorder.respond(httpx.Response(200, json=[{"id": 1, "name": "a"}]))
    assert models.list_repos() == [Repo(id=1, name="a")]


def test_with_options_passes_through(models, recorder):
    recorder.respond(httpx.Response(200, json=[]))
    models.with_options(headers={"X-A": "1"}).list_repos()
    assert recorder.last.headers["X-A"] == "1"


@pytest.mark.anyio
async def test_aio(models, recorder):
    recorder.respond(httpx.Response(201, json={"id": 2, "name": "b"}))
    assert await models.aio.create_repo(NewRepo(name="b")) == Repo(id=2, name="b")
