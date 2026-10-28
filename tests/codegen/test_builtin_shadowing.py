from apiroute.codegen.builtin_shadowing import BuiltinShadowing


def test_annotations_name_shadowed_builtins_explicitly():
    shadowing = BuiltinShadowing(["list", "get", "create"])
    assert shadowing.qualified("list[dict[str, Any]]") == "builtins.list[dict[str, Any]]"
    assert shadowing.qualified("per_page: int | None = None") == "per_page: int | None = None"
    assert shadowing.used


def test_only_names_a_method_shadows():
    shadowing = BuiltinShadowing(["dict", "list"])
    assert shadowing.qualified("list[dict[str, Any]]") == "builtins.list[builtins.dict[str, Any]]"


def test_strings_and_attributes_are_left_alone():
    shadowing = BuiltinShadowing(["list"])
    annotation = 'list_id: Annotated[str, Header("list")]'
    assert shadowing.qualified(annotation) == annotation
    assert shadowing.qualified("typing.list") == "typing.list"
    assert not shadowing.used


def test_no_shadowing():
    shadowing = BuiltinShadowing(["get_item", "listing"])
    assert shadowing.qualified("list[str]") == "list[str]"
    assert not shadowing.used
