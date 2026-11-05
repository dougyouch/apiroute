import importlib

import pytest

from apiroute.codegen.cli import main
from apiroute.codegen.openapi.openapi_reader import OpenApiReader
from tests.conftest import needs_pydantic

SPEC = """\
openapi: 3.1.0
info: {title: Pet Store, version: "1"}
servers: [{url: "https://pets.test"}]
paths:
  /pets:
    get:
      operationId: listPets
      tags: [pets]
      responses:
        "200":
          description: ok
          content:
            application/json:
              schema: {type: array, items: {$ref: "#/components/schemas/Pet"}}
webhooks:
  newPet:
    post:
      summary: A pet was added.
      requestBody:
        content:
          application/json:
            schema: {$ref: "#/components/schemas/Pet"}
  pet-sold:
    post:
      requestBody:
        $ref: "#/components/requestBodies/Sale"
  import:
    $ref: "#/components/pathItems/Batch"
  ping:
    post:
      responses: {"200": {description: ok}}
  mood:
    post:
      requestBody:
        content:
          application/json:
            schema: {type: string, enum: [happy, sad]}
components:
  requestBodies:
    Sale:
      content:
        application/json:
          schema:
            type: object
            required: [petId]
            properties:
              petId: {type: integer}
              price: {type: number}
  pathItems:
    Batch:
      put:
        requestBody:
          content:
            application/json:
              schema: {type: array, items: {$ref: "#/components/schemas/Pet"}}
  schemas:
    Pet:
      type: object
      required: [id]
      properties:
        id: {type: integer}
        name: {type: string}
"""


@pytest.fixture
def spec(tmp_path):
    path = tmp_path / "pets.yaml"
    path.write_text(SPEC)
    return path


def test_the_reader_finds_each_webhook(spec):
    pytest.importorskip("yaml")
    definition = OpenApiReader(str(spec), "PetsApi").read()
    found = {w.wire_name: w for w in definition.webhooks}
    assert [w.name for w in definition.webhooks] == [
        "new_pet",
        "pet_sold",
        "import_",
        "ping",
        "mood",
    ]
    assert found["mood"].payload.expr == "Literal['happy', 'sad']"
    assert found["newPet"].summary == "A pet was added."
    assert found["newPet"].payload.expr == "Pet"
    assert found["pet-sold"].payload.expr == "PetSoldPayload"
    assert found["import"].payload.expr == "list[Pet]"
    assert (found["ping"].payload, found["ping"].payload_plain) == (None, "Any")
    assert found["newPet"].payload_plain == "dict[str, Any]"


def test_a_spec_without_webhooks_has_no_webhooks_module(tmp_path):
    pytest.importorskip("yaml")
    spec = tmp_path / "plain.yaml"
    spec.write_text(SPEC.split("webhooks:")[0] + "components:" + SPEC.split("components:")[1])
    out = tmp_path / "plain"
    assert main(["generate", "openapi", str(spec), "-o", str(out), "--models"]) == 0
    assert not (out / "webhooks.py").exists()
    assert not (out / "models" / "webhooks.py").exists()


def generated(tmp_path, monkeypatch, spec, *flags, name="petstore"):
    out = tmp_path / name
    assert main(["generate", "openapi", str(spec), "-o", str(out), *flags]) == 0
    monkeypatch.syspath_prepend(str(tmp_path))
    return out


def test_the_dict_layer_parses_json(tmp_path, monkeypatch, spec):
    pytest.importorskip("yaml")
    generated(tmp_path, monkeypatch, spec, name="petstore_dicts")
    webhooks = importlib.import_module("petstore_dicts.webhooks")
    assert webhooks.new_pet(b'{"id": 1}') == {"id": 1}
    assert webhooks.ping("null") is None
    assert webhooks.WEBHOOKS == {
        "newPet": webhooks.new_pet,
        "pet-sold": webhooks.pet_sold,
        "import": webhooks.import_,
        "ping": webhooks.ping,
        "mood": webhooks.mood,
    }


@needs_pydantic
def test_the_models_layer_returns_payload_models(tmp_path, monkeypatch, spec):
    from pydantic import ValidationError

    generated(tmp_path, monkeypatch, spec, "--models", name="petstore_models")
    webhooks = importlib.import_module("petstore_models.models.webhooks")
    pet = webhooks.new_pet(b'{"id": 1, "name": "Rex"}')
    assert (type(pet).__name__, pet.name) == ("Pet", "Rex")
    sale = webhooks.pet_sold({"petId": 3, "price": 9.5})
    assert (type(sale).__name__, sale.pet_id) == ("PetSoldPayload", 3)
    assert [p.id for p in webhooks.import_(b'[{"id": 1}, {"id": 2}]')] == [1, 2]
    assert webhooks.ping(b'{"any": "thing"}') == {"any": "thing"}
    # like a route's return annotation, a type without a model in it isn't converted
    assert webhooks.mood(b'"happy"') == "happy"
    with pytest.raises(ValidationError):
        webhooks.new_pet(b'{"name": "no id"}')


def test_regenerating_without_webhooks_removes_the_modules(tmp_path, monkeypatch, spec):
    pytest.importorskip("yaml")
    out = generated(tmp_path, monkeypatch, spec, "--models")
    assert (out / "webhooks.py").exists()
    spec.write_text(SPEC.split("webhooks:")[0] + "components:" + SPEC.split("components:")[1])
    assert main(["generate", "openapi", str(spec), "-o", str(out), "--models"]) == 0
    assert not (out / "webhooks.py").exists()
    assert not (out / "models" / "webhooks.py").exists()
