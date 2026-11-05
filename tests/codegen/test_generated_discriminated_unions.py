import importlib

import pytest

from apiroute.codegen.cli import main
from tests.conftest import needs_pydantic

pytestmark = needs_pydantic

SPEC = """\
openapi: 3.1.0
info: {title: Pets, version: "1"}
servers: [{url: "https://pets.test"}]
paths:
  /owners/{id}:
    get:
      operationId: getOwner
      parameters: [{name: id, in: path, required: true, schema: {type: integer}}]
      responses:
        "200":
          description: ok
          content:
            application/json:
              schema: {$ref: "#/components/schemas/Owner"}
components:
  schemas:
    Cat:
      type: object
      required: [petType, meows]
      properties:
        petType: {type: string}
        meows: {type: boolean}
    Dog:
      type: object
      properties:
        petType: {type: string, enum: [dog, puppy, wolf]}
        barks: {type: boolean}
    Pet:
      oneOf: [{$ref: "#/components/schemas/Cat"}, {$ref: "#/components/schemas/Dog"}]
      discriminator:
        propertyName: petType
        mapping: {cat: "#/components/schemas/Cat", dog: Dog, puppy: Dog}
    Owner:
      type: object
      properties:
        favourite: {$ref: "#/components/schemas/Pet"}
        pets: {type: array, items: {$ref: "#/components/schemas/Pet"}}
        other:
          oneOf: [{$ref: "#/components/schemas/Cat"}, {$ref: "#/components/schemas/Dog"}]
          discriminator: {propertyName: petType}
"""


def generate(tmp_path, monkeypatch, *flags):
    spec = tmp_path / "pets.yaml"
    spec.write_text(SPEC)
    name = "pets_" + "_".join(flag.strip("-").replace("-", "_") for flag in flags)
    out = tmp_path / name
    command = ["generate", "openapi", str(spec), "-o", str(out), "--models", "--discriminators"]
    assert main([*command, *flags]) == 0
    monkeypatch.syspath_prepend(str(tmp_path))
    return importlib.import_module(f"{name}.models.models"), out


def test_the_member_is_picked_by_its_tag(tmp_path, monkeypatch):
    models, _ = generate(tmp_path, monkeypatch)
    owner = models.Owner.model_validate(
        {
            "favourite": {"petType": "cat", "meows": True},
            "pets": [{"petType": "puppy", "barks": True}, {"petType": "dog"}],
            "other": {"petType": "Dog"},
        }
    )
    assert type(owner.favourite).__name__ == "Cat"
    assert [type(p).__name__ for p in owner.pets] == ["Dog", "Dog"]
    assert type(owner.other).__name__ == "Dog"


def test_an_unknown_tag_names_the_expected_ones(tmp_path, monkeypatch):
    from pydantic import ValidationError

    models, _ = generate(tmp_path, monkeypatch)
    with pytest.raises(ValidationError, match="does not match any of the expected tags"):
        models.Owner.model_validate({"favourite": {"petType": "fish"}})


def test_errors_are_reported_for_the_tagged_member_only(tmp_path, monkeypatch):
    from pydantic import ValidationError

    models, _ = generate(tmp_path, monkeypatch)
    with pytest.raises(ValidationError) as raised:
        models.Owner.model_validate({"favourite": {"petType": "cat"}})
    assert [e["loc"] for e in raised.value.errors()] == [("favourite", "cat", "meows")]


def test_the_generated_alias(tmp_path, monkeypatch):
    _, out = generate(tmp_path, monkeypatch)
    source = (out / "models" / "schemas" / "pet.py").read_text()
    assert 'Pet = Annotated[Cat | Dog, Field(discriminator="pet_type")]' in source


@pytest.mark.parametrize(
    "flags", [("--nullable-fields",), ("--open-enums",), ("--nullable-fields", "--open-enums")]
)
def test_nullable_fields_and_open_enums_leave_tags_closed(tmp_path, monkeypatch, flags):
    models, _ = generate(tmp_path, monkeypatch, *flags)
    owner = models.Owner.model_validate({"favourite": {"petType": "dog", "barks": None}})
    assert type(owner.favourite).__name__ == "Dog"


def test_discriminators_only_apply_to_openapi(tmp_path, capsys):
    wsdl = tmp_path / "x.wsdl"
    wsdl.write_text("<definitions/>")
    assert main(["generate", "wsdl", str(wsdl), "-o", str(tmp_path / "x"), "--discriminators"]) == 1
    assert "--discriminators only applies to openapi" in capsys.readouterr().err
