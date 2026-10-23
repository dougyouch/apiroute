import pytest

from apiroute.codegen.openapi.ref_resolver import RefResolver
from apiroute.codegen.openapi.schema_mapper import SchemaMapper

DOCUMENT = {
    "components": {
        "schemas": {
            "Node": {
                "type": "object",
                "properties": {
                    "children": {"type": "array", "items": {"$ref": "#/components/schemas/Node"}}
                },
            },
            "Color": {"type": "string", "enum": ["red", "green"]},
        }
    }
}


@pytest.fixture
def mapper():
    models = {}
    return SchemaMapper(RefResolver(DOCUMENT, "spec.yaml"), models), models


@pytest.mark.parametrize(
    ("schema", "expr"),
    [
        ({"type": "integer"}, "int"),
        ({"type": "string", "nullable": True}, "str | None"),
        ({"type": ["number", "null"]}, "float | None"),
        ({"type": ["string", "integer"]}, "str | int"),
        ({"enum": ["a", "b", None]}, "Literal['a', 'b'] | None"),
        ({"const": 3}, "Literal[3]"),
        ({"type": "array", "items": {"type": "boolean"}}, "list[bool]"),
        ({"type": "object", "additionalProperties": {"type": "integer"}}, "dict[str, int]"),
        ({"type": "object"}, "dict[str, Any]"),
        (
            {"oneOf": [{"type": "string"}, {"type": "integer"}, {"type": "null"}]},
            "str | int | None",
        ),
        ({}, "Any"),
    ],
)
def test_plain_types(mapper, schema, expr):
    assert mapper[0].map(schema, "Hint").expr == expr


def test_inline_objects_become_named_models(mapper):
    mapped = mapper[0].map(
        {
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "integer"}, "fullName": {"type": "string"}},
        },
        "user",
    )
    model = mapper[1]["User"]
    assert mapped.expr == "User" and mapped.models == {"User"}
    assert [(f.name, f.alias, f.type.expr, f.required) for f in model.fields] == [
        ("id", None, "int", True),
        ("full_name", "fullName", "str", False),
    ]


def test_recursive_refs_name_themselves(mapper):
    assert mapper[0].map({"$ref": "#/components/schemas/Node"}, "x").expr == "Node"
    assert mapper[1]["Node"].fields[0].type.expr == "list[Node]"


def test_named_enums_become_aliases(mapper):
    mapper[0].map({"$ref": "#/components/schemas/Color"}, "x")
    assert mapper[1]["Color"].alias_of.expr == "Literal['red', 'green']"


def test_plain_shapes_for_the_dict_layer(mapper):
    plain = mapper[0].plain
    assert plain({"$ref": "#/components/schemas/Node"}) == "dict[str, Any]"
    assert plain({"type": "array"}) == "list[Any]"
    assert plain({"type": "string"}) == "str"
    assert plain({"oneOf": []}) == "Any"
