from apiroute.codegen.graphql.graphql_type_mapper import GraphQLTypeMapper
from apiroute.codegen.graphql.operation_collector import OperationCollector
from apiroute.codegen.graphql.operation_documents import OperationDocuments
from apiroute.codegen.graphql.selection_model_mapper import SelectionModelMapper
from tests.codegen.graphql.helpers import SCHEMA, write_operations


def map_result(tmp_path, text, fragments=""):
    files = {"op.graphql": text}
    if fragments:
        files["fragments.graphql"] = fragments
    collected = OperationCollector(write_operations(tmp_path / "ops", files)).collect()
    docs = OperationDocuments(SCHEMA, collected)
    assert docs.problems() == []
    models, taken = {}, set()
    types = GraphQLTypeMapper(models, taken, {})
    mapper = SelectionModelMapper(SCHEMA, docs.collector, types, models, taken)
    operation = collected.operations[0]
    prepared, _ = docs.prepared(operation)
    ref = mapper.result(prepared, operation.node.name.value)
    return ref, models


def fields(model):
    return {f.name: (f.alias, f.type.expr, f.required) for f in model.fields}


def test_nested_models_are_named_after_their_path(tmp_path):
    ref, models = map_result(
        tmp_path,
        'query Repo { repository(owner: "a", name: "b") { name stargazerCount owner { login } } }',
    )
    assert ref.expr == "RepoResult"
    assert fields(models["RepoResult"]) == {"repository": (None, "RepoRepository | None", True)}
    assert fields(models["RepoRepository"]) == {
        "name": (None, "str", True),
        "stargazer_count": ("stargazerCount", "int", True),
        "owner": (None, "RepoRepositoryOwner", True),
    }
    assert fields(models["RepoRepositoryOwner"]) == {"login": (None, "str", True)}


def test_aliases_name_fields_and_models(tmp_path):
    _, models = map_result(
        tmp_path, 'query Repo { repo: repository(owner: "a", name: "b") { by: owner { login } } }'
    )
    assert fields(models["RepoResult"]) == {"repo": (None, "RepoRepo | None", True)}
    assert fields(models["RepoRepo"]) == {"by": (None, "RepoRepoBy", True)}


def test_lists_keep_item_nullability_and_descriptions_carry_over(tmp_path):
    _, models = map_result(
        tmp_path,
        'query Repo { repository(owner: "a", name: "b") { topics languages } viewer { name } }',
    )
    assert fields(models["RepoRepository"]) == {
        "topics": (None, "list[str] | None", True),
        "languages": (None, "list[str | None] | None", True),
    }
    assert models["RepoViewer"].fields[0].description == "The user's display name."


def test_conditional_fields_default_to_none(tmp_path):
    _, models = map_result(
        tmp_path,
        "query V($full: Boolean!) { viewer { login name @include(if: $full) "
        "... @skip(if: $full) { url } } }",
    )
    assert fields(models["VViewer"]) == {
        "login": (None, "str", True),
        "name": (None, "str | None", False),
        "url": (None, "Any", False),
    }


def test_fragments_are_flattened_and_fields_merge(tmp_path):
    _, models = map_result(
        tmp_path,
        "query V { viewer { ...A repositories(first: 1) { totalCount } } }",
        "fragment A on User { login repositories(first: 1) { nodes { name } } }",
    )
    assert fields(models["VViewer"]) == {
        "login": (None, "str", True),
        "repositories": (None, "VViewerRepositories", True),
    }
    assert fields(models["VViewerRepositories"]) == {
        "nodes": (None, "list[VViewerRepositoriesNodes]", True),
        "total_count": ("totalCount", "int", True),
    }


def test_a_union_with_type_conditions(tmp_path):
    _, models = map_result(
        tmp_path,
        'query S { search(query: "q", type: USER) '
        "{ ... on User { login } ... on Repository { name } } }",
    )
    assert fields(models["SResult"]) == {"search": (None, "list[SSearch]", True)}
    assert models["SSearch"].alias_of.expr == "SSearchUser | SSearchRepository | SSearchOther"
    assert fields(models["SSearchUser"]) == {
        "typename": ("__typename", 'Literal["User"]', True),
        "login": (None, "str", True),
    }
    assert fields(models["SSearchOther"]) == {"typename": ("__typename", "str", True)}


def test_no_fallback_when_every_possible_type_is_named(tmp_path):
    _, models = map_result(
        tmp_path,
        'query R { repository(owner: "a", name: "b") { owner { login '
        "... on User { name } ... on Organization { members } } } }",
    )
    union = models["RRepositoryOwner"].alias_of.expr
    assert union == "RRepositoryOwnerUser | RRepositoryOwnerOrganization"
    assert "Other" not in union
    assert fields(models["RRepositoryOwnerOrganization"])["members"] == (None, "int", True)
    assert fields(models["RRepositoryOwnerUser"])["login"] == (None, "str", True)


def test_interface_conditions_are_optional_in_the_fallback(tmp_path):
    _, models = map_result(
        tmp_path,
        'query S { search(query: "q", type: USER) { ... on User { login } ... on Node { id } } }',
    )
    assert fields(models["SSearchUser"]) == {
        "typename": ("__typename", 'Literal["User"]', True),
        "login": (None, "str", True),
        "id": (None, "str", True),
    }
    assert fields(models["SSearchOther"]) == {
        "typename": ("__typename", "str", True),
        "id": (None, "str", False),
    }


def test_an_interface_without_type_conditions_is_one_model(tmp_path):
    _, models = map_result(tmp_path, 'query N { node(id: "1") { id __typename } }')
    assert fields(models["NNode"]) == {
        "id": (None, "str", True),
        "typename": ("__typename", "str", True),
    }


def test_mutations_use_the_mutation_root(tmp_path):
    ref, models = map_result(
        tmp_path, 'mutation Star { addStar(input: {starrableId: "x"}) { clientMutationId } }'
    )
    assert fields(models["StarResult"]) == {"add_star": ("addStar", "StarAddStar | None", True)}
