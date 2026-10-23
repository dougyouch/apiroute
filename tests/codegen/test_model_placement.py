from apiroute.codegen.api_definition import ApiDefinition, Group, Model, ModelField, Operation
from apiroute.codegen.model_placement import ModelPlacement
from apiroute.codegen.type_ref import TypeRef


def returning(name):
    return Operation("op", "GET", "/", response=TypeRef.model(name))


def test_models_live_with_their_only_tag_and_shared_ones_at_the_root():
    definition = ApiDefinition("Api", None)
    definition.models = {
        "Repo": Model("Repo", [ModelField("owner", None, TypeRef.model("User"), True)]),
        "User": Model("User"),
        "Issue": Model("Issue", [ModelField("author", None, TypeRef.model("User"), True)]),
        "Label": Model("Label"),
        "Status": Model("Status"),
    }
    definition.groups = [
        Group("repos", "ReposSection", operations=[returning("Repo")]),
        Group("issues", "IssuesSection", operations=[returning("Issue"), returning("Label")]),
    ]
    definition.root = Group("", "Api", operations=[returning("Status")])
    placement = ModelPlacement(definition).place()
    assert placement == {
        "Repo": "repos",
        "Issue": "issues",
        "Label": "issues",
        "User": "",  # used by both tags
        "Status": "",
    }


def test_a_root_models_dependencies_move_to_the_root():
    definition = ApiDefinition("Api", None)
    definition.models = {
        "Shared": Model("Shared", [ModelField("detail", None, TypeRef.model("Detail"), True)]),
        "Detail": Model("Detail"),
    }
    definition.root = Group("", "Api", operations=[returning("Shared")])
    definition.groups = [Group("tag", "TagSection", operations=[returning("Detail")])]
    assert ModelPlacement(definition).place() == {"Shared": "", "Detail": ""}
