import json

from apiroute.codegen.openapi.swagger2_converter import Swagger2Converter
from tests.codegen.conftest import FIXTURES


def converted():
    return Swagger2Converter().convert(json.loads((FIXTURES / "swagger2.json").read_text()))


def test_servers_schemas_and_refs():
    document = converted()
    assert document["servers"] == [{"url": "https://old.test/api"}]
    assert "User" in document["components"]["schemas"]
    get = document["paths"]["/users/{id}"]["get"]
    assert get["responses"]["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/User"
    }
    assert get["parameters"][0]["schema"] == {"type": "integer"}


def test_body_and_form_parameters_become_request_bodies():
    paths = converted()["paths"]
    put = paths["/users/{id}"]["put"]
    assert put["requestBody"]["required"] is True
    assert [p["name"] for p in put["parameters"]] == ["id"]
    form = paths["/avatars"]["post"]["requestBody"]["content"]["multipart/form-data"]["schema"]
    assert form["properties"]["image"] == {"type": "string", "format": "binary"}
    assert form["required"] == ["image"]


def test_basic_auth_becomes_http_basic():
    assert converted()["components"]["securitySchemes"]["basic"] == {
        "type": "http",
        "scheme": "basic",
    }
