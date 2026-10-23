from dataclasses import dataclass, field

import pytest

from apiroute.dataclass_converter import DataclassConverter


@dataclass
class Owner:
    login: str


@dataclass
class Repo:
    name: str
    owner: Owner
    topics: list[str] = field(default_factory=list)
    parent: "Repo | None" = None


def test_builds_nested_dataclasses_and_ignores_unknown_keys():
    data = {"name": "api", "owner": {"login": "ann", "id": 1}, "stars": 5}
    assert DataclassConverter(Repo).convert(data) == Repo("api", Owner("ann"))


def test_lists_dicts_and_optional_fields():
    data = [{"name": "a", "owner": {"login": "x"}, "parent": None}]
    assert DataclassConverter(list[Repo]).convert(data) == [Repo("a", Owner("x"))]
    by_name = DataclassConverter(dict[str, Owner]).convert({"a": {"login": "x"}})
    assert by_name == {"a": Owner("x")}
    fork = {"name": "b", "owner": {"login": "y"}, "parent": {"name": "a", "owner": {"login": "x"}}}
    assert DataclassConverter(Repo).convert(fork).parent == Repo("a", Owner("x"))


def test_missing_fields_and_wrong_shapes_raise():
    with pytest.raises(TypeError):
        DataclassConverter(Owner).convert({})
    with pytest.raises(TypeError, match="needs an object"):
        DataclassConverter(Owner).convert(["x"])
