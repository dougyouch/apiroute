from apiroute.codegen.alias_inliner import AliasInliner
from apiroute.codegen.api_definition import ApiDefinition, Model
from apiroute.codegen.type_ref import TypeRef


def inliner():
    definition = ApiDefinition("Api", None)
    definition.models = {
        "Color": Model("Color", alias_of=TypeRef("Literal['red', 'blue']")),
        "Size": Model("Size", alias_of=TypeRef("int | str")),
        "Colors": Model("Colors", alias_of=TypeRef("list[Color]", frozenset({"Color"}))),
        "Pet": Model("Pet"),
    }
    return AliasInliner(definition)


def test_plain_aliases_are_spelled_out():
    assert inliner().plain(TypeRef.model("Color")) == "Literal['red', 'blue']"
    assert inliner().plain(TypeRef.model("Colors")) == "list[Literal['red', 'blue']]"
    assert inliner().plain(TypeRef("list[Size]", frozenset({"Size"}))) == "list[(int | str)]"


def test_anything_naming_a_model_class_is_any():
    assert inliner().plain(TypeRef("list[Pet]", frozenset({"Pet"}))) == "Any"
