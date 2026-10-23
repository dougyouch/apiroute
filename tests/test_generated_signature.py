import inspect

import pytest

from apiroute import FROM_CLIENT, Client, RouteDefinitionError, route


def params(method):
    return {
        name: (param.kind.name, param.default)
        for name, param in inspect.signature(method).parameters.items()
    }


class Api(Client):
    base_url = "https://x.test"
    org: str
    region = "eu"

    @property
    def team(self):
        return "core"

    get_user = route("/users/:username")
    list_repos = route(
        "/orgs/{org}/{region}/repos", query={"page": "{page}"}, body={"team": "{team}"}
    )
    create_thing = route("/things")
    update_thing = route("/things/:id", body={"name": "{name}"})
    upload = route("POST", "/raw", body="<ping/>")


def test_placeholders_become_required_keyword_only_parameters():
    assert params(Api.get_user) == {
        "self": ("POSITIONAL_OR_KEYWORD", inspect.Parameter.empty),
        "username": ("KEYWORD_ONLY", inspect.Parameter.empty),
    }


def test_names_the_class_declares_fall_back_to_the_client():
    signature = params(Api.list_repos)
    assert list(signature) == ["self", "org", "region", "page", "team"]
    assert signature["org"][1] is FROM_CLIENT  # annotation
    assert signature["region"][1] is FROM_CLIENT  # class attribute
    assert signature["team"][1] is FROM_CLIENT  # property
    assert signature["page"][1] is inspect.Parameter.empty


def test_body_methods_without_a_body_template_take_an_optional_body():
    assert params(Api.create_thing)["body"] == ("KEYWORD_ONLY", None)
    assert "body" not in params(Api.update_thing)
    assert "body" not in params(Api.upload)
    assert "body" not in params(Api.get_user)


def test_bound_methods_hide_self_and_keep_a_docstring():
    assert str(inspect.signature(Api().get_user)) == "(*, username)"
    assert Api.get_user.__doc__ == "GET /users/:username"
    assert Api.get_user.__name__ == "get_user"


def test_bad_templates_fail_at_class_creation_with_the_route_name():
    with pytest.raises(RouteDefinitionError, match=r"Bad.get_x: .*object values"):

        class Bad(Client):
            get_x = route("/x", query={"when": object()})


def test_bad_methods_fail_at_class_creation():
    with pytest.raises(RouteDefinitionError, match="unknown HTTP method"):

        class Bad(Client):
            get_x = route("FETCH", "/x")
