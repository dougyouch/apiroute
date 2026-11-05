import importlib
import json

import httpx
import pytest

from apiroute.codegen.cli import main
from apiroute.testing import (
    MockResponseMismatch,
    MockTransport,
    ResponseSchemas,
    cassette,
    mock_transport,
)
from tests.conftest import needs_pydantic

pytestmark = needs_pydantic

SPEC = """\
openapi: 3.0.0
info: {title: Pets, version: "1"}
servers: [{url: "https://pets.test"}]
paths:
  /pets:
    get:
      operationId: listPets
      tags: [pets]
      parameters: [{name: page, in: query, schema: {type: integer}}]
      responses:
        "200":
          description: ok
          content:
            application/json:
              schema: {type: array, items: {$ref: "#/components/schemas/Pet"}}
  /pets/{id}:
    get:
      operationId: getPet
      tags: [pets]
      parameters: [{name: id, in: path, required: true, schema: {type: integer}}]
      responses:
        "200":
          description: ok
          content:
            application/json:
              schema: {$ref: "#/components/schemas/Pet"}
  /stores:
    get:
      operationId: listStores
      tags: [stores]
      responses:
        "200":
          description: ok
          content:
            application/json:
              schema: {type: array, items: {$ref: "#/components/schemas/Store"}}
  /health:
    get:
      operationId: health
      responses:
        "200": {description: ok, content: {text/plain: {schema: {type: string}}}}
  /status:
    get:
      operationId: status
      responses:
        "200":
          description: ok
          content:
            application/json:
              schema: {type: object, required: [up], properties: {up: {type: boolean}}}
components:
  schemas:
    Store:
      type: object
      required: [id]
      properties:
        id: {type: integer}
    Pet:
      type: object
      required: [id, name]
      properties:
        id: {type: integer}
        name: {type: string}
"""

PAGINATION = """\
- name: pages
  has_parameter: [page]
  paginate: {type: page}
"""


@pytest.fixture(scope="module")
def client_class(tmp_path_factory):
    root = tmp_path_factory.mktemp("schemas")
    (root / "pets.yaml").write_text(SPEC)
    (root / "rules.yaml").write_text(PAGINATION)
    out = root / "pets_checked"
    command = ["generate", "openapi", str(root / "pets.yaml"), "-o", str(out), "--models"]
    assert main([*command, "--pagination", str(root / "rules.yaml")]) == 0
    import sys

    sys.path.insert(0, str(root))
    try:
        return importlib.import_module("pets_checked").PetsCheckedApi
    finally:
        sys.path.remove(str(root))


def test_finds_each_routes_model(client_class):
    schemas = ResponseSchemas(client_class)
    pets = client_class.pets
    assert schemas.model_for(pets, "get_pet").__name__ == "Pet"
    assert str(schemas.model_for(pets, "list_pets")).startswith("list[")
    assert schemas.model_for(client_class, "status").__name__ == "StatusResponse"
    assert schemas.model_for(client_class, "health") is str  # text: only JSON is checked
    assert schemas.model_for(client_class, "nope") is None


def test_only_the_calling_sections_models_are_imported(client_class):
    import sys

    package = client_class.__module__.rsplit(".", 1)[0]
    mock = MockTransport(check=ResponseSchemas(client_class))
    mock.on(operation="getPet").respond(httpx.Response(200, json={"id": 1, "name": "Rex"}))
    client_class(transport=mock).pets.get_pet(1)
    loaded = {name for name in sys.modules if name.startswith(package)}
    assert f"{package}.pets.models.client" in loaded
    assert f"{package}.pets.models.schemas.pet" in loaded
    assert not any(name.startswith(f"{package}.stores") for name in loaded)


def test_a_mock_that_fits_passes(client_class):
    mock = MockTransport(check=ResponseSchemas(client_class))
    mock.on(operation="getPet").respond(httpx.Response(200, json={"id": 1, "name": "Rex"}))
    assert client_class(transport=mock).pets.get_pet(1) == {"id": 1, "name": "Rex"}


def test_a_mock_that_has_drifted_fails(client_class):
    mock = MockTransport(check=ResponseSchemas(client_class))
    mock.on(operation="getPet").respond(httpx.Response(200, json={"id": 1}))
    with pytest.raises(
        MockResponseMismatch, match=r"getPet: GET https://pets.test/pets/1: .*Pet"
    ) as raised:
        client_class(transport=mock).pets.get_pet(1)
    assert "name" in str(raised.value)


def test_lists_are_checked_item_by_item(client_class):
    with mock_transport(check=ResponseSchemas(client_class)) as mock:
        mock.on(operation="listPets").respond(
            httpx.Response(200, json=[{"id": 1, "name": "a"}, {"id": "x"}])
        )
        with pytest.raises(MockResponseMismatch):
            client_class().pets.list_pets()


def test_error_statuses_and_bodies_that_arent_json_pass(client_class):
    mock = MockTransport(check=ResponseSchemas(client_class))
    mock.on(operation="getPet").respond(httpx.Response(404, json={"message": "no"}))
    mock.on(operation="health").respond(httpx.Response(200, text="ok"))
    mock.on(operation="status").respond(httpx.Response(200, content=b'{"wrong": 1}'))
    api = client_class(transport=mock)
    with pytest.raises(Exception, match="404"):
        api.pets.get_pet(1)
    assert api.health() == "ok"
    assert api.status() == {"wrong": 1}  # no JSON content type: not checked


def test_each_page_of_a_paginated_method_is_checked(client_class):
    mock = MockTransport(check=ResponseSchemas(client_class))
    mock.on(operation="listPets").respond(
        httpx.Response(200, json=[{"id": 1, "name": "a"}]),
        httpx.Response(200, json=[{"id": 2}]),
    )
    pets = client_class(transport=mock).pets.list_pets_all()
    assert next(pets) == {"id": 1, "name": "a"}  # the first page fits
    with pytest.raises(MockResponseMismatch, match=r"listPets: GET https://pets.test/pets\?page=2"):
        next(pets)


def test_pages_that_fit_pass(client_class):
    mock = MockTransport(check=ResponseSchemas(client_class))
    mock.on(operation="listPets").respond(
        httpx.Response(200, json=[{"id": 1, "name": "a"}]), httpx.Response(200, json=[])
    )
    assert [pet.id for pet in client_class(transport=mock).pets.models.list_pets_all()] == [1]


@pytest.mark.anyio
async def test_async_pages_are_checked(client_class):
    mock = MockTransport(check=ResponseSchemas(client_class))
    mock.on(operation="listPets").respond(httpx.Response(200, json=[{"id": "x"}]))
    pets = client_class(async_transport=mock.aio).aio.pets.list_pets_all()
    with pytest.raises(MockResponseMismatch):
        await pets.__anext__()


def test_paginated_routes_without_a_one_page_method_pass_unchecked():
    from apiroute import Client, route
    from apiroute.pagination import PageNumber

    class Api(Client):
        base_url = "https://x.test"
        everything = route("/everything", paginate=PageNumber())  # no _all suffix
        list_things_all = route("/things", paginate=PageNumber())  # no list_things
        get_one = route("/one", operation="other")
        get_one_all = route("/one", paginate=PageNumber())  # a different operation

    schemas = ResponseSchemas(Api)
    mock = MockTransport(check=schemas)
    for path in ("/everything", "/things"):
        mock.on(path=path).respond(httpx.Response(200, json=[1]), httpx.Response(200, json=[]))
    mock.on(path="/one").respond(httpx.Response(200, json=[1]), httpx.Response(200, json=[]))
    api = Api(transport=mock)
    assert list(api.everything()) == [1]
    assert list(api.list_things_all()) == [1]
    assert list(api.get_one_all()) == [1]


def test_calls_through_other_clients_pass_unchecked(client_class):
    from apiroute import Client, route

    class Other(Client):
        base_url = "https://pets.test"
        get_pet = route("/pets/{id}", operation="getPet")

    mock = MockTransport(check=ResponseSchemas(client_class))
    mock.on(operation="getPet").respond(httpx.Response(200, json={"id": 1}))
    assert Other(transport=mock).get_pet(id=1) == {"id": 1}


@pytest.mark.anyio
async def test_async_calls_are_checked(client_class):
    mock = MockTransport(check=ResponseSchemas(client_class))
    mock.on(operation="status").respond(httpx.Response(200, json={}))
    with pytest.raises(MockResponseMismatch):
        await client_class(async_transport=mock.aio).aio.status()


def test_replayed_cassettes_are_checked(client_class, tmp_path):
    path = tmp_path / "pets.json"
    interaction = {
        "request": {"method": "GET", "url": "https://pets.test/pets/1", "headers": [], "body": {}},
        "response": {
            "status": 200,
            "headers": [["content-type", "application/json"]],
            "body": {"json": {"id": 1}},
        },
    }
    path.write_text(json.dumps({"version": 1, "interactions": [interaction]}))
    with cassette(path, check=ResponseSchemas(client_class)), pytest.raises(MockResponseMismatch):
        client_class().pets.get_pet(1)


def test_hand_written_clients_and_unknown_operations_pass_unchecked():
    from apiroute import Client, Section, route

    class Admin(Section):
        get_stats = route("/stats")

    class Api(Client):
        base_url = "https://x.test"
        get_x = route("/x")
        admin = Admin

    schemas = ResponseSchemas(Api)
    mock = MockTransport(check=schemas)
    mock.on(path="/x").respond(httpx.Response(200, json={"anything": True}))
    mock.on(path="/stats").respond(httpx.Response(200, json=[]))
    api = Api(transport=mock)
    assert api.get_x() == {"anything": True}
    assert api.admin.get_stats() == []
    assert schemas.model_for(Admin, "get_stats") is None
