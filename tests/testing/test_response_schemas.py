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


def test_finds_each_operations_model_sections_included(client_class):
    schemas = ResponseSchemas(client_class)
    assert schemas.model_for("getPet").__name__ == "Pet"
    assert str(schemas.model_for("listPets")).startswith("list[")
    assert schemas.model_for("status").__name__ == "StatusResponse"
    assert schemas.model_for("health") is str  # a text response: only JSON ones are checked
    assert schemas.model_for("nope") is None


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


def test_paginated_all_methods_check_each_page(client_class):
    mock = MockTransport(check=ResponseSchemas(client_class))
    mock.on(operation="listPets").respond(httpx.Response(200, json=[{"id": 1}]))
    with pytest.raises(MockResponseMismatch):
        list(client_class(transport=mock).pets.list_pets_all())


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
        also_admin = Admin  # the same section twice is walked once

    schemas = ResponseSchemas(Api)
    mock = MockTransport(check=schemas)
    mock.on(path="/x").respond(httpx.Response(200, json={"anything": True}))
    mock.on(path="/stats").respond(httpx.Response(200, json=[]))
    api = Api(transport=mock)
    assert api.get_x() == {"anything": True}
    assert api.admin.get_stats() == []
    assert schemas.model_for("get_stats") is None
