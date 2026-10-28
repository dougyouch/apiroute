import json

import httpx
import pytest

from apiroute import HttpxClientTransport
from apiroute.codegen.openapi.openapi_reader import OpenApiReader
from apiroute.codegen.operation_names import OperationNames
from tests.codegen.conftest import FIXTURES
from tests.conftest import needs_pydantic

# Stripe-style names for the shop fixture: sections nest, and pets.adopt has a level above it
# (pets) that keeps methods of its own
NAMES = {
    "listPets": "pets.list",
    "Pets_getPet": "pets.retrieve",
    "createPet": "pets.adopt.create",
    "getPhoto": "pets.photos.retrieve",
    "placeOrder": "store.orders.create",
    "getStatus": "health.status",
}


def read():
    return OpenApiReader(str(FIXTURES / "shop.yaml"), "ShopApi").read()


def named(names=NAMES):
    definition = read()
    OperationNames(names).apply(definition)
    return definition


def methods(definition):
    groups = [definition.root, *definition.groups]
    return {group.name: [operation.name for operation in group.operations] for group in groups}


def test_operations_move_to_nested_sections_and_unnamed_ones_stay():
    assert methods(named()) == {
        "": [],
        "health": ["status"],
        "pets": ["delete_pet", "upload_photo", "list", "retrieve"],
        "pets.adopt": ["create"],
        "pets.photos": ["retrieve"],
        "store": ["list"],  # the receipt route, unnamed, stays in its tag
        "store.orders": ["create"],
    }


def test_sections_are_created_with_the_levels_above_them():
    definition = named({"getStatus": "ops.health.status"})
    groups = {group.name: group.class_name for group in definition.groups}
    assert groups["ops"] == "OpsSection" and groups["ops.health"] == "OpsHealthSection"
    assert methods(definition)["ops"] == []  # kept: a level with sections below it


def test_a_tag_left_empty_is_dropped():
    definition = named({"placeOrder": "orders.create", "list": "orders.receipt"})
    assert "store" not in methods(definition)


def test_names_matching_no_operation_are_warnings():
    definition = named({"getStatus": "status", "gone": "x.y"})
    assert definition.warnings == ["--operation-names: no operation 'gone'"]


@pytest.mark.parametrize(
    ("names", "problem"),
    [
        ({"listPets": "pets.get", "Pets_getPet": "pets.get"}, "pets.get: both listPets and"),
        ({"listPets": "pets.photos", "getPhoto": "pets.photos.get"}, "has a section's name"),
        ({"listPets": "pets.models"}, "pets.models: listPets has a reserved name"),
    ],
)
def test_clashing_names_are_errors(names, problem):
    with pytest.raises(ValueError, match="--operation-names: .*" + problem.replace(".", r"\.")):
        named(names)


def test_operations_can_be_keyed_by_method_and_spec_path():
    definition = named({"DELETE /pets/{pet-id}": "pets.remove", "GET /status": "health.ping"})
    assert methods(definition)["pets"][-1] == "remove"
    assert methods(definition)["health"] == ["ping"]
    assert definition.warnings == []


def test_operations_without_an_operation_id_can_be_named(tmp_path):
    spec = tmp_path / "api.yaml"
    spec.write_text(
        "openapi: 3.0.0\n"
        "info: {title: Weather, version: '1'}\n"
        "paths:\n"
        "  /api/data/metar:\n"
        "    get:\n"
        "      tags: [Weather Data]\n"
        "      responses: {'200': {description: ok}}\n"
        "  /api/data/taf:\n"
        "    get:\n"
        "      tags: [Weather Data]\n"
        "      responses: {'200': {description: ok}}\n"
    )
    definition = OpenApiReader(str(spec), "WeatherApi").read()
    assert methods(definition)["weather_data"] == ["get_api_data_metar", "get_api_data_taf"]
    names = {"GET /api/data/metar": "metars.get", "GET /api/data/taf": "metars.get"}
    with pytest.raises(ValueError, match="both GET /api/data/metar and GET /api/data/taf"):
        OperationNames(names).apply(definition)
    definition = OpenApiReader(str(spec), "WeatherApi").read()
    OperationNames({"GET /api/data/metar": "metar", "GET /api/data/taf": "taf"}).apply(definition)
    assert methods(definition) == {"": ["metar", "taf"]}


def test_names_become_python_names():
    definition = named({"listPets": "Pet-Shop.listAll", "getStatus": "class"})
    assert methods(definition)["pet_shop"] == ["list_all"]
    assert methods(definition)[""] == ["class_"]


def test_load_reads_a_json_file(tmp_path):
    path = tmp_path / "names.json"
    path.write_text(json.dumps(NAMES))
    assert (
        methods(named())["pets.adopt"]
        == methods(_applied(OperationNames.load(str(path))))["pets.adopt"]
    )
    path.write_text("[]")
    with pytest.raises(ValueError, match="expected a JSON object"):
        OperationNames.load(str(path))


def _applied(names):
    definition = read()
    names.apply(definition)
    return definition


@pytest.fixture
def api(generate, recorder):
    shop = generate("shop.yaml", operation_names=NAMES)
    mock = httpx.MockTransport(recorder)
    client = HttpxClientTransport(httpx.Client(transport=mock))
    return shop, shop.ShopApi(token="t", api_key="k", partner="p", transport=client)


def test_nested_sections_call_their_routes(api, recorder):
    shop, client = api
    recorder.respond(httpx.Response(200, content=b"\x89PNG"))
    assert client.pets.photos.retrieve(3) == b"\x89PNG"
    assert str(recorder.last.url).startswith("https://eu.shop.test/v1/pets/3/photo")
    assert recorder.last.headers["Authorization"] == "Bearer t"  # inherited through two levels
    assert type(client.pets.photos).__name__ == "PetsPhotosSection"
    assert not hasattr(client, "get_status") and client.health.status


@needs_pydantic
def test_typed_calls_in_nested_sections_use_models_from_any_level(api, recorder):
    shop, client = api
    recorder.respond(httpx.Response(201, json={"id": 5, "name": "Rex", "createdAt": None}))
    pet = client.pets.adopt.models.create(body={"name": "Rex", "status": "available"})
    assert type(pet).__name__ == "Pet" and pet.id == 5
    recorder.respond(httpx.Response(200, json={"id": 3, "status": "placed"}))
    assert client.store.orders.models.create(body={"pet_id": 1}).status == "placed"
