import pytest

from apiroute.pagination.dotted_path import DottedPath


def test_reads_nested_keys():
    assert DottedPath("a.b").read({"a": {"b": 3}}) == 3


def test_empty_path_is_the_body():
    assert DottedPath("").read([1, 2]) == [1, 2]
    assert DottedPath("").list_in([1, 2]) == [1, 2]


def test_missing_keys_and_non_objects_read_as_none():
    assert DottedPath("a.b").read({"a": None}) is None
    assert DottedPath("a.b").read({"a": [1]}) is None
    assert DottedPath("a").read(None) is None


def test_list_in_names_the_path_when_it_is_not_a_list():
    with pytest.raises(ValueError, match="items 'data' is a dict, not a list"):
        DottedPath("data").list_in({"data": {}})
    with pytest.raises(ValueError, match="items 'data' is missing"):
        DottedPath("data").list_in({})
    with pytest.raises(ValueError, match="the body is a dict"):
        DottedPath("").list_in({})
