import pytest

from apiroute.query_encoder import QueryEncoder


def test_flat_repeats_list_names_and_formats_booleans():
    pairs = QueryEncoder("flat").encode({"tag": ["a", "b"], "open": True, "n": 2})
    assert pairs == [("tag", "a"), ("tag", "b"), ("open", "true"), ("n", "2")]


def test_flat_rejects_dicts():
    with pytest.raises(TypeError, match="nested"):
        QueryEncoder("flat").encode({"user": {"name": "Ann"}})


def test_nested_uses_brackets_like_the_gem():
    pairs = QueryEncoder("nested").encode(
        {"user": {"name": "Ann", "tags": ["a"]}, "items": [{"id": 1}]}
    )
    assert pairs == [("user[name]", "Ann"), ("user[tags][]", "a"), ("items[][id]", "1")]


def test_rejects_unknown_styles():
    with pytest.raises(ValueError):
        QueryEncoder("rails")
