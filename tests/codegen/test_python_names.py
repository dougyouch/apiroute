import pytest

from apiroute.codegen.python_names import pascal_case, safe_identifier, snake_case, unique


def test_snake_case():
    assert snake_case("getRepoByID") == "get_repo_by_id"
    assert snake_case("repos/list-for-org") == "repos_list_for_org"
    assert snake_case("X-Request-Id") == "x_request_id"
    assert snake_case("from") == "from_"
    assert snake_case("2fa") == "n2fa"


def test_pascal_case():
    assert pascal_case("pull-request review") == "PullRequestReview"
    assert pascal_case("class") == "Class"


def test_safe_identifier():
    assert safe_identifier("match") == "match_"  # soft keyword


def test_unique_skips_taken_and_reserved_names():
    taken = {"list"}
    assert unique("list", taken) == "list_2"
    assert unique("models", taken) == "models_2"  # reserved: the .models view
    assert unique("models", set(), frozenset()) == "models"


def test_soft_keywords_are_the_same_on_every_python():
    from apiroute.codegen.python_names import safe_identifier

    assert [safe_identifier(n) for n in ("type", "match", "case", "kind")] == [
        "type_",
        "match_",
        "case_",
        "kind",
    ]


def test_client_hooks_and_settings_are_reserved():
    from apiroute.codegen.python_names import unique

    taken: set[str] = set()
    names = [
        "idempotent",
        "idempotency_key",
        "follow_redirects",
        "check_response",
        "redact_url",
        "soap_header",
    ]
    assert [unique(name, taken) for name in names] == [f"{name}_2" for name in names]


def test_no_model_field_shadows_base_model():
    """pydantic warns about a field named after any attribute BaseModel has, those it gets
    from its metaclass (register, mro) too, which dir(BaseModel) doesn't list. model_ names
    are pydantic's own namespace, left out here."""
    import warnings

    from apiroute.codegen.python_names import MODEL_RESERVED

    pydantic = pytest.importorskip("pydantic")

    names = {*dir(pydantic.BaseModel), *dir(type(pydantic.BaseModel))}
    public = {name for name in names if not name.startswith(("_", "model_"))}
    for name in sorted(public):
        field = unique(name, set(), MODEL_RESERVED)
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            pydantic.create_model("Model", **{field: (int, 0)})
