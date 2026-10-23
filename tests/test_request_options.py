import pytest

from apiroute.request_options import RequestOptions


def test_merged_combines_dicts_and_overrides_scalars():
    base = RequestOptions(headers={"A": "1"}, timeout=5, returns="text")
    merged = base.merged(RequestOptions(headers={"B": "2"}, retries=3))
    assert merged == RequestOptions(
        headers={"A": "1", "B": "2"}, timeout=5, retries=3, returns="text"
    )


def test_rejects_unknown_return_modes():
    with pytest.raises(ValueError):
        RequestOptions(returns="xml")


def test_merged_bodies_combine_and_keep_none_markers():
    merged = RequestOptions(body={"a": 1, "b": 2}).merged(RequestOptions(body={"b": None}))
    assert merged.body == {"a": 1, "b": None}


def test_merged_non_dict_body_replaces():
    assert RequestOptions(body={"a": 1}).merged(RequestOptions(body=[1])).body == [1]
    assert RequestOptions(body={"a": 1}).merged(RequestOptions()).body == {"a": 1}
