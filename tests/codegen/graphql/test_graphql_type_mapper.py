import graphql

from apiroute.codegen.graphql.graphql_type_mapper import GraphQLTypeMapper
from tests.codegen.graphql.helpers import SCHEMA


def mapper(scalars=None):
    models = {}
    return GraphQLTypeMapper(models, set(), scalars or {}), models


def test_builtin_scalars():
    types, models = mapper()
    scalars = graphql.specified_scalar_types.values()  # Int, Float, String, Boolean, ID
    exprs = sorted(types.leaf(scalar).expr for scalar in scalars)
    assert exprs == ["bool", "float", "int", "str", "str"]
    assert models == {}


def test_custom_scalars_are_any_unless_mapped():
    types, models = mapper({"DateTime": ("datetime", "datetime")})
    assert types.leaf(SCHEMA.get_type("URI")).expr == "Any"
    assert types.leaf(SCHEMA.get_type("DateTime")).expr == "DateTime"
    alias = models["DateTime"]
    assert (alias.alias_of.expr, alias.imports) == ("datetime", {"datetime": "datetime"})


def test_enums_are_literal_aliases_made_once():
    types, models = mapper()
    first = types.leaf(SCHEMA.get_type("Visibility"))
    assert types.leaf(SCHEMA.get_type("Visibility")) == first
    assert models["Visibility"].alias_of.expr == 'Literal["PUBLIC", "PRIVATE", "INTERNAL"]'


def test_input_objects_with_aliases_defaults_and_recursion():
    types, models = mapper()
    ref = types.input(SCHEMA.get_type("AddStarInput"))
    assert ref.expr == "AddStarInput | None"
    fields = {f.name: (f.alias, f.type.expr, f.required) for f in models["AddStarInput"].fields}
    assert fields == {
        "starrable_id": ("starrableId", "str", True),
        "client_mutation_id": ("clientMutationId", "str | None", False),
        "tags": (None, "list[StarTag] | None", False),
    }
    star_tag = {f.name: (f.type.expr, f.required) for f in models["StarTag"].fields}
    assert star_tag == {"name": ("str", True), "parent": ("StarTag | None", False)}
    assert models["StarTag"].description == "Tags a star."


def test_required_input_drops_only_the_outer_nullability():
    types, _ = mapper()
    list_type = graphql.GraphQLList(graphql.GraphQLNonNull(graphql.GraphQLInt))
    assert types.required_input(list_type).expr == "list[int]"
    assert types.input(list_type).expr == "list[int] | None"
    nullable_items = graphql.GraphQLNonNull(graphql.GraphQLList(graphql.GraphQLInt))
    assert types.required_input(nullable_items).expr == "list[int | None]"


def test_only_reached_types_become_models():
    types, models = mapper()
    types.input(SCHEMA.get_type("StarTag"))
    assert sorted(models) == ["StarTag"]
