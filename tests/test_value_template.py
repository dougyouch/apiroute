import pytest

from apiroute.value_template import ValueTemplate


def test_whole_placeholder_keeps_the_type():
    template = ValueTemplate({"limit": "{limit}", "tags": "{tags}"})
    values = {"limit": 50, "tags": ["a", "b"]}
    assert template.render(values.__getitem__) == {"limit": 50, "tags": ["a", "b"]}


def test_placeholders_inside_text_are_formatted():
    template = ValueTemplate({"q": "author:{user} state:{state}"})
    values = {"user": "octocat", "state": "open"}
    assert template.render(values.__getitem__) == {"q": "author:octocat state:open"}


def test_nested_lists_and_literals():
    template = ValueTemplate({"user": {"name": "{name}", "roles": ["admin", "{role}"]}, "n": 1})
    rendered = template.render({"name": "Ann", "role": "dev"}.__getitem__)
    assert rendered == {"user": {"name": "Ann", "roles": ["admin", "dev"]}, "n": 1}


def test_collects_names():
    template = ValueTemplate({"a": "{x}", "b": ["{y} and {z}"], "c": "plain"})
    assert template.names == ("x", "y", "z")


def test_renders_fresh_containers_each_time():
    template = ValueTemplate({"a": [1]})
    first = template.render(lambda name: None)
    first["a"].append(2)
    assert template.render(lambda name: None) == {"a": [1]}


def test_rejects_other_objects():
    with pytest.raises(TypeError, match="set values"):
        ValueTemplate({"a": {1, 2}})
