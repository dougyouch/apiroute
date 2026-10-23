import pytest

from apiroute.http_method import infer_http_method, normalize_http_method


@pytest.mark.parametrize(
    ("name", "method"),
    [
        ("get_user", "GET"),
        ("create_user", "POST"),
        ("post", "POST"),
        ("add_item", "POST"),
        ("insert_row", "POST"),
        ("update_user", "PUT"),
        ("change_plan", "PUT"),
        ("patch_user", "PATCH"),
        ("delete_user", "DELETE"),
        ("remove", "DELETE"),
        ("destroy_all", "DELETE"),
        ("posts", "GET"),
        ("addresses", "GET"),
        ("deleted_users", "GET"),
        ("updates_feed", "GET"),
    ],
)
def test_infer_http_method(name, method):
    assert infer_http_method(name) == method


def test_normalize_http_method_uppercases():
    assert normalize_http_method("post") == "POST"


def test_normalize_http_method_rejects_unknown_verbs():
    with pytest.raises(ValueError, match="FETCH"):
        normalize_http_method("FETCH")
