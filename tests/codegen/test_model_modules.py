from apiroute.codegen.api_definition import ApiDefinition, Model, ModelField
from apiroute.codegen.model_modules import ModelModules
from apiroute.codegen.type_ref import TypeRef


def field(name, *refs):
    return ModelField(name, None, TypeRef(" | ".join(refs), frozenset(refs)), False)


def test_cycles_share_a_module_and_the_rest_get_their_own():
    definition = ApiDefinition("Api", None)
    definition.models = {
        "Pet": Model("Pet", [field("owner", "Owner")]),
        "Owner": Model("Owner", [field("pets", "Pet"), field("address", "Address")]),
        "Address": Model("Address"),
        "Tag": Model("Tag", alias_of=TypeRef("str")),
    }
    placement = dict.fromkeys(definition.models, "")
    modules = ModelModules(definition, placement).modules()
    assert modules["Pet"] is modules["Owner"]
    assert modules["Pet"].name == "owner" and modules["Pet"].models == ("Owner", "Pet")
    assert modules["Address"].name == "address"
    assert modules["Tag"].name == "tag"


def test_deep_chains_do_not_hit_the_recursion_limit():
    definition = ApiDefinition("Api", None)
    definition.models = {
        f"M{i}": Model(f"M{i}", [field("next", f"M{i + 1}")] if i < 5000 else [])
        for i in range(5001)
    }
    modules = ModelModules(definition, dict.fromkeys(definition.models, "")).modules()
    assert len({id(m) for m in modules.values()}) == 5001
