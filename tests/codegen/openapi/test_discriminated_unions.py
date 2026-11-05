import pytest

from apiroute.codegen.openapi.ref_resolver import RefResolver
from apiroute.codegen.openapi.schema_mapper import SchemaMapper


def pet(name, extra=None, required=("petType",)):
    return {
        "type": "object",
        "required": list(required),
        "properties": {"petType": {"type": "string"}, **(extra or {})},
    }


SCHEMAS = {
    "Cat": pet("Cat", {"meows": {"type": "boolean"}}),
    "Dog": pet("Dog", {"barks": {"type": "boolean"}}, required=()),
    "Fish": {"type": "object", "properties": {"fins": {"type": "integer"}}},
    "Pet": {
        "oneOf": [{"$ref": "#/components/schemas/Cat"}, {"$ref": "#/components/schemas/Dog"}],
        "discriminator": {
            "propertyName": "petType",
            "mapping": {"cat": "#/components/schemas/Cat", "dog": "Dog", "puppy": "Dog"},
        },
    },
    "ImplicitPet": {
        "anyOf": [{"$ref": "#/components/schemas/Cat"}, {"$ref": "#/components/schemas/Dog"}],
        "discriminator": {"propertyName": "petType"},
    },
    "MaybePet": {
        "oneOf": [
            {"$ref": "#/components/schemas/Cat"},
            {"$ref": "#/components/schemas/Dog"},
            {"type": "null"},
        ],
        "discriminator": {"propertyName": "petType"},
    },
    "Untaggable": {
        "oneOf": [{"$ref": "#/components/schemas/Cat"}, {"$ref": "#/components/schemas/Fish"}],
        "discriminator": {"propertyName": "petType"},
    },
}


@pytest.fixture
def mapper():
    models = {}
    document = {"components": {"schemas": SCHEMAS}}
    return SchemaMapper(RefResolver(document, "spec.yaml"), models, discriminators=True), models


def field(models, model, name):
    return next(f for f in models[model].fields if f.name == name)


def test_a_named_union_becomes_an_annotated_alias(mapper):
    mapper, models = mapper
    assert mapper.map({"$ref": "#/components/schemas/Pet"}, "x").expr == "Pet"
    assert models["Pet"].alias_of.expr == 'Annotated[Cat | Dog, Field(discriminator="pet_type")]'
    assert models["Pet"].alias_of.models == {"Cat", "Dog"}


def test_members_get_the_literal_of_their_mapping_values_and_must_have_it(mapper):
    mapper, models = mapper
    mapper.map({"$ref": "#/components/schemas/Pet"}, "x")
    cat, dog = field(models, "Cat", "pet_type"), field(models, "Dog", "pet_type")
    assert (cat.type.expr, cat.required, cat.discriminator) == ("Literal['cat']", True, ("cat",))
    assert (dog.type.expr, dog.required) == ("Literal['dog', 'puppy']", True)


def test_without_a_mapping_the_schema_name_is_the_value(mapper):
    mapper, models = mapper
    mapper.map({"$ref": "#/components/schemas/ImplicitPet"}, "x")
    assert field(models, "Cat", "pet_type").type.expr == "Literal['Cat']"


def test_a_member_in_two_unions_takes_both_values(mapper):
    mapper, models = mapper
    mapper.map({"$ref": "#/components/schemas/Pet"}, "x")
    mapper.map({"$ref": "#/components/schemas/ImplicitPet"}, "x")
    assert field(models, "Cat", "pet_type").type.expr == "Literal['cat', 'Cat']"


def test_a_nullable_union_stays_nullable(mapper):
    mapper, models = mapper
    mapper.map({"$ref": "#/components/schemas/MaybePet"}, "x")
    expr = models["MaybePet"].alias_of.expr
    assert expr == 'Annotated[Cat | Dog, Field(discriminator="pet_type")] | None'


def test_an_inline_union_becomes_an_alias_model(mapper):
    mapper, models = mapper
    schema = {
        "oneOf": [{"$ref": "#/components/schemas/Cat"}, {"$ref": "#/components/schemas/Dog"}],
        "discriminator": {"propertyName": "petType"},
    }
    assert mapper.map(schema, "OwnerPet").expr == "OwnerPet"
    assert models["OwnerPet"].alias_of.expr.startswith("Annotated[Cat | Dog")
    assert mapper.map({**schema, "nullable": True}, "OwnerPet").expr == "OwnerPet_2 | None"


def test_a_member_without_the_property_leaves_a_plain_union(mapper):
    mapper, models = mapper
    mapper.map({"$ref": "#/components/schemas/Untaggable"}, "x")
    assert models["Untaggable"].alias_of.expr == "Cat | Fish"
    assert field(models, "Cat", "pet_type").type.expr == "str"


@pytest.mark.parametrize(
    "options",
    [
        [{"$ref": "#/components/schemas/Cat"}, {"type": "string"}],
        [
            {"$ref": "#/components/schemas/Cat"},
            {"type": "object", "properties": {"petType": {"type": "string"}}},
        ],
        [{"$ref": "#/components/schemas/Cat"}],
    ],
)
def test_unions_that_cant_be_tagged_stay_plain(mapper, options):
    mapper, models = mapper
    union = mapper.map({"oneOf": options, "discriminator": {"propertyName": "petType"}}, "U")
    assert "Annotated" not in union.expr
    assert field(models, "Cat", "pet_type").discriminator == ()


@pytest.mark.parametrize("discriminator", [None, "petType", {"mapping": {}}])
def test_without_a_usable_discriminator_the_union_is_plain(mapper, discriminator):
    mapper, _ = mapper
    options = [{"$ref": "#/components/schemas/Cat"}, {"$ref": "#/components/schemas/Dog"}]
    schema = (
        {"oneOf": options}
        if discriminator is None
        else {"oneOf": options, "discriminator": discriminator}
    )
    assert mapper.map(schema, "U").expr == "Cat | Dog"


def test_an_inline_member_named_in_the_mapping_is_ok(mapper):
    mapper, models = mapper
    schema = {
        "oneOf": [{"$ref": "#/components/schemas/Cat"}, {"$ref": "#/components/schemas/Dog"}],
        "discriminator": {"propertyName": "petType", "mapping": {"kitty": "Cat"}},
    }
    mapper.map(schema, "U")
    assert field(models, "Cat", "pet_type").type.expr == "Literal['kitty']"
    assert field(models, "Dog", "pet_type").type.expr == "Literal['Dog']"


def test_unions_stay_plain_unless_asked_for():
    models = {}
    document = {"components": {"schemas": SCHEMAS}}
    mapper = SchemaMapper(RefResolver(document, "spec.yaml"), models)
    mapper.map({"$ref": "#/components/schemas/Pet"}, "x")
    assert models["Pet"].alias_of.expr == "Cat | Dog"
    assert field(models, "Cat", "pet_type").type.expr == "str"


def test_members_whose_property_has_different_python_names_stay_plain():
    models = {}
    schemas = {
        **SCHEMAS,
        "Odd": {
            "type": "object",
            "properties": {"pet_type": {"type": "string"}, "petType": {"type": "string"}},
        },
    }
    mapper = SchemaMapper(
        RefResolver({"components": {"schemas": schemas}}, "spec.yaml"), models, discriminators=True
    )
    union = mapper.map(
        {
            "oneOf": [{"$ref": "#/components/schemas/Cat"}, {"$ref": "#/components/schemas/Odd"}],
            "discriminator": {"propertyName": "petType"},
        },
        "U",
    )
    assert union.expr == "Cat | Odd"


def test_mapping_entries_that_arent_text_are_skipped(mapper):
    mapper, models = mapper
    schema = {
        "oneOf": [{"$ref": "#/components/schemas/Cat"}, {"$ref": "#/components/schemas/Dog"}],
        "discriminator": {"propertyName": "petType", "mapping": {"cat": 7}},
    }
    mapper.map(schema, "U")
    assert field(models, "Cat", "pet_type").type.expr == "Literal['Cat']"
