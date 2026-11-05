import json

import pytest
import yaml

from apiroute.codegen.cli import BREAKING_EXIT, main
from apiroute.codegen.diff.api_differ import ApiDiffer
from apiroute.codegen.diff.diff_report import DiffReport
from apiroute.codegen.openapi.openapi_reader import OpenApiReader

BASE = {
    "openapi": "3.1.0",
    "info": {"title": "Pets", "version": "1"},
    "servers": [{"url": "https://pets.test"}],
    "paths": {
        "/pets/{id}": {
            "get": {
                "operationId": "getPet",
                "tags": ["pets"],
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}},
                    {"name": "fields", "in": "query", "schema": {"type": "string"}},
                ],
                "responses": {
                    "200": {
                        "description": "ok",
                        "content": {
                            "application/json": {"schema": {"$ref": "#/components/schemas/Pet"}}
                        },
                    }
                },
            },
            "put": {
                "operationId": "updatePet",
                "tags": ["pets"],
                "parameters": [
                    {"name": "id", "in": "path", "required": True, "schema": {"type": "integer"}}
                ],
                "requestBody": {
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/PetInput"}}
                    }
                },
                "responses": {"204": {"description": "done"}},
            },
        },
        "/health": {"get": {"operationId": "health", "responses": {"200": {"description": "ok"}}}},
    },
    "webhooks": {
        "petAdded": {
            "post": {
                "requestBody": {
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Pet"}}
                    }
                }
            }
        }
    },
    "components": {
        "schemas": {
            "Pet": {
                "type": "object",
                "required": ["id", "name"],
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "status": {"type": "string", "enum": ["available", "sold"]},
                },
            },
            "PetInput": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "tag": {"type": "string"}},
            },
            "Color": {"type": "string", "enum": ["red", "green"]},
        }
    },
}


def changed(edit):
    spec = json.loads(json.dumps(BASE))
    edit(spec)
    return spec


def changes(tmp_path, edit, **reader):
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    old.write_text(json.dumps(BASE))
    new.write_text(json.dumps(changed(edit)))
    definitions = [OpenApiReader(str(p), "Api", **reader).read() for p in (old, new)]
    return {(c.kind, str(c)) for c in ApiDiffer(*definitions).changes()}


def op(spec, path="/pets/{id}", method="get"):
    return spec["paths"][path][method]


def schema(spec, name):
    return spec["components"]["schemas"][name]


def test_no_changes(tmp_path):
    assert changes(tmp_path, lambda spec: None) == set()


def test_descriptions_dont_count(tmp_path):
    assert (
        changes(tmp_path, lambda s: op(s).update(summary="Fetch a pet", description="x")) == set()
    )


def test_a_removed_operation_breaks_and_an_added_one_adds(tmp_path):
    def edit(spec):
        del spec["paths"]["/health"]
        spec["paths"]["/stores"] = {
            "get": {"operationId": "listStores", "responses": {"200": {"description": "ok"}}}
        }

    assert changes(tmp_path, edit) == {
        ("breaking", "GET /health: removed (health)"),
        ("addition", "GET /stores: added (list_stores)"),
    }


def test_a_renamed_method_breaks(tmp_path):
    assert changes(tmp_path, lambda s: op(s).update(operationId="fetchPet")) == {
        ("breaking", "GET /pets/{}: method renamed pets.get_pet -> pets.fetch_pet"),
    }


def test_a_new_tag_moves_the_method_to_another_section(tmp_path):
    assert ("breaking", "GET /pets/{}: method renamed pets.get_pet -> animals.get_pet") in changes(
        tmp_path, lambda s: op(s).update(tags=["animals"])
    )


def test_renaming_a_path_parameter_changes_no_route(tmp_path):
    def edit(spec):
        item = spec["paths"].pop("/pets/{id}")
        for operation in item.values():
            operation["parameters"][0]["name"] = "petId"
        spec["paths"]["/pets/{petId}"] = item

    assert changes(tmp_path, edit) == {
        ("breaking", "GET /pets/{}: path parameter id removed"),
        ("breaking", "GET /pets/{}: path parameter petId added, required"),
        ("breaking", "PUT /pets/{}: path parameter id removed"),
        ("breaking", "PUT /pets/{}: path parameter petId added, required"),
    }


def test_parameters(tmp_path):
    def edit(spec):
        params = op(spec)["parameters"]
        params[1]["required"] = True
        params.append({"name": "expand", "in": "query", "schema": {"type": "boolean"}})
        params.append(
            {"name": "X-Tenant", "in": "header", "required": True, "schema": {"type": "string"}}
        )

    assert changes(tmp_path, edit) == {
        ("breaking", "GET /pets/{}: query parameter fields is now required"),
        ("addition", "GET /pets/{}: query parameter expand added"),
        ("breaking", "GET /pets/{}: header parameter X-Tenant added, required"),
    }


def test_parameter_removed_and_retyped(tmp_path):
    def edit(spec):
        op(spec)["parameters"][1] = {"name": "fields", "in": "query", "schema": {"type": "integer"}}
        op(spec, method="put")["parameters"] = []

    assert changes(tmp_path, edit) == {
        ("breaking", "GET /pets/{}: query parameter fields type str -> int"),
        ("breaking", "PUT /pets/{}: path parameter id removed"),
    }


def test_request_bodies(tmp_path):
    def edit(spec):
        op(spec, method="put")["requestBody"]["required"] = True
        op(spec, method="put")["requestBody"]["content"] = {
            "application/x-www-form-urlencoded": op(spec, method="put")["requestBody"]["content"][
                "application/json"
            ]
        }
        op(spec)["requestBody"] = {"content": {"application/json": {"schema": {"type": "object"}}}}

    assert changes(tmp_path, edit) == {
        ("breaking", "PUT /pets/{}: request body is now required"),
        ("breaking", "PUT /pets/{}: request body format json -> form"),
        ("addition", "GET /pets/{}: request body added"),
    }


def test_removed_and_required_new_bodies_break(tmp_path):
    def edit(spec):
        del op(spec, method="put")["requestBody"]
        op(spec)["requestBody"] = {
            "required": True,
            "content": {"application/json": {"schema": {"type": "object"}}},
        }

    assert changes(tmp_path, edit) == {
        ("breaking", "PUT /pets/{}: request body removed"),
        ("breaking", "GET /pets/{}: request body added, required"),
    }


def test_a_retyped_response_breaks(tmp_path):
    response = {
        "description": "ok",
        "content": {
            "application/json": {
                "schema": {"type": "array", "items": {"$ref": "#/components/schemas/Pet"}}
            }
        },
    }
    assert changes(tmp_path, lambda s: op(s)["responses"].update({"200": response})) == {
        ("breaking", "GET /pets/{}: response Pet -> list[Pet]"),
    }


def test_received_models(tmp_path):
    def edit(spec):
        pet = schema(spec, "Pet")
        pet["required"] = ["id"]
        del pet["properties"]["name"]
        pet["properties"]["age"] = {"type": "integer"}
        pet["properties"]["status"]["enum"].append("pending")
        pet["properties"]["id"]["type"] = "string"

    assert changes(tmp_path, edit) == {
        ("breaking", "Pet.name: removed"),
        ("addition", "Pet.age: added"),
        (
            "addition",
            "Pet.status: type Literal['available', 'sold'] -> "
            "Literal['available', 'sold', 'pending']",
        ),
        ("breaking", "Pet.id: type int -> str"),
    }


def test_a_received_field_that_may_now_be_missing_breaks(tmp_path):
    assert changes(tmp_path, lambda s: schema(s, "Pet").update(required=["id"])) == {
        ("breaking", "Pet.name: now optional"),
    }


def test_a_narrowed_enum_breaks(tmp_path):
    assert changes(
        tmp_path, lambda s: schema(s, "Pet")["properties"]["status"].update(enum=["sold"])
    ) == {
        ("breaking", "Pet.status: type Literal['available', 'sold'] -> Literal['sold']"),
    }


def test_sent_models(tmp_path):
    def edit(spec):
        inp = schema(spec, "PetInput")
        inp["required"] = ["name"]
        inp["properties"]["owner"] = {"type": "string"}
        inp["properties"]["code"] = {"type": "string"}
        inp["required"].append("code")

    assert changes(tmp_path, edit) == {
        ("breaking", "PetInput.name: now required"),
        ("addition", "PetInput.owner: added"),
        ("breaking", "PetInput.code: added, required"),
    }


def test_a_sent_field_becoming_optional_is_an_addition(tmp_path):
    def edit(spec):
        schema(spec, "PetInput")["required"] = []

    base_required = changed(lambda s: schema(s, "PetInput").update(required=["name"]))
    old, new = tmp_path / "old.json", tmp_path / "new.json"
    old.write_text(json.dumps(base_required))
    new.write_text(json.dumps(BASE))
    definitions = [OpenApiReader(str(p), "Api").read() for p in (old, new)]
    assert {str(c) for c in ApiDiffer(*definitions).changes() if c.kind == "addition"} == {
        "PetInput.name: now optional"
    }


def test_models_added_removed_and_aliases(tmp_path):
    def edit(spec):
        schemas = spec["components"]["schemas"]
        schemas["Color"]["enum"] = ["red", "green", "blue"]
        schemas["Store"] = {"type": "object", "properties": {"id": {"type": "integer"}}}

    assert changes(tmp_path, edit) == {
        ("addition", "model Color: Literal['red', 'green'] -> Literal['red', 'green', 'blue']"),
        ("addition", "model Store: added"),
    }
    assert ("breaking", "model Color: removed") in changes(
        tmp_path, lambda s: s["components"]["schemas"].pop("Color")
    )


def test_a_model_becoming_an_alias_breaks(tmp_path):
    assert ("breaking", "model PetInput: a model -> str") in changes(
        tmp_path, lambda s: s["components"]["schemas"].update(PetInput={"type": "string"})
    )


def test_webhooks(tmp_path):
    def edit(spec):
        spec["webhooks"] = {"petSold": spec["webhooks"].pop("petAdded")}

    assert changes(tmp_path, edit) == {
        ("breaking", "webhook petAdded: removed"),
        ("addition", "webhook petSold: added"),
    }


def test_the_report(tmp_path):
    report = DiffReport([])
    assert report.commit_type == "none"
    assert report.text() == "No changes to the generated client.\nSuggested commit type: none\n"
    from apiroute.codegen.diff.api_change import ApiChange

    report = DiffReport([ApiChange("addition", "GET /x", "added (x)")])
    assert report.commit_type == "feat"
    report = DiffReport(
        [ApiChange("addition", "GET /x", "added (x)"), ApiChange("breaking", "model A", "removed")]
    )
    assert report.commit_type == "feat!"
    assert report.text() == (
        "Breaking changes (1):\n  - model A: removed\nAdditions (1):\n  + GET /x: added (x)\n"
        "Suggested commit type: feat!\n"
    )
    assert json.loads(report.json()) == {
        "commit_type": "feat!",
        "breaking": [{"subject": "model A", "detail": "removed"}],
        "additions": [{"subject": "GET /x", "detail": "added (x)"}],
    }


@pytest.fixture
def specs(tmp_path):
    old, new = tmp_path / "old.yaml", tmp_path / "new.yaml"
    old.write_text(yaml.safe_dump(BASE))
    new.write_text(yaml.safe_dump(changed(lambda s: s["paths"].pop("/health"))))
    return old, new


def test_the_cli(specs, capsys):
    old, new = specs
    assert main(["diff", str(old), str(new)]) == 0
    out = capsys.readouterr().out
    assert "GET /health: removed (health)" in out
    assert out.endswith("Suggested commit type: feat!\n")


def test_the_cli_fails_on_breaking_changes_when_asked(specs, capsys):
    old, new = specs
    assert main(["diff", str(old), str(new), "--fail-on-breaking"]) == BREAKING_EXIT
    assert main(["diff", str(old), str(old), "--fail-on-breaking"]) == 0


def test_the_cli_writes_json(specs, capsys):
    old, new = specs
    main(["diff", str(old), str(new), "--format", "json"])
    assert json.loads(capsys.readouterr().out)["commit_type"] == "feat!"


def test_the_cli_reports_errors(tmp_path, capsys):
    assert main(["diff", str(tmp_path / "nope.yaml"), str(tmp_path / "nope.yaml")]) == 1
    assert "apiroute:" in capsys.readouterr().err


def test_operation_names_apply_to_both_sides(specs, tmp_path, capsys):
    old, _ = specs
    renamed = tmp_path / "renamed.yaml"
    renamed.write_text(yaml.safe_dump(changed(lambda s: op(s).update(operationId="fetchPet"))))
    names = tmp_path / "names.json"
    names.write_text(json.dumps({"getPet": "pets.get", "fetchPet": "pets.get"}))
    assert main(["diff", str(old), str(renamed), "--operation-names", str(names)]) == 0
    assert "No changes" in capsys.readouterr().out


def test_discriminators_compare_tagged_unions(tmp_path):
    def tagged(spec):
        schemas = spec["components"]["schemas"]
        schemas["Cat"] = {"type": "object", "properties": {"kind": {"type": "string"}}}
        schemas["Dog"] = {
            "type": "object",
            "properties": {"kind": {"type": "string"}, "barks": {"type": "boolean"}},
        }
        schemas["Animal"] = {
            "oneOf": [{"$ref": "#/components/schemas/Cat"}, {"$ref": "#/components/schemas/Dog"}],
            "discriminator": {"propertyName": "kind"},
        }

    old, new = tmp_path / "old.json", tmp_path / "new.json"
    old.write_text(json.dumps(changed(tagged)))
    new.write_text(
        json.dumps(
            changed(
                lambda s: (tagged(s), s["components"]["schemas"]["Dog"]["properties"].pop("kind"))
            )
        )
    )
    definitions = [OpenApiReader(str(p), "Api", discriminators=True).read() for p in (old, new)]
    found = {str(c) for c in ApiDiffer(*definitions).changes()}
    assert "Dog.kind: removed" in found
    assert "Cat.kind: type Literal['Cat'] -> str" in found  # no longer a tagged union
    assert any(s.startswith("model Animal: Annotated[Cat | Dog") for s in found)


def test_a_retyped_request_body(tmp_path):
    def edit(spec):
        body = op(spec, method="put")["requestBody"]["content"]["application/json"]
        body["schema"] = {"type": "array", "items": {"$ref": "#/components/schemas/PetInput"}}

    assert ("breaking", "PUT /pets/{}: request body PetInput -> list[PetInput]") in changes(
        tmp_path, edit
    )


def test_recursive_models(tmp_path):
    def edit(spec):
        pet = schema(spec, "Pet")
        pet["properties"]["parent"] = {"$ref": "#/components/schemas/Pet"}

    assert changes(tmp_path, edit) == {("addition", "Pet.parent: added")}
