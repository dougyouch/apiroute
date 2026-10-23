from typing import Annotated

import pytest

from apiroute import Body, Client, Header, Query, RouteDefinitionError, route


def definition(cls, name):
    return vars(cls)[name].definition


def test_infers_the_method_and_binds_placeholders():
    class Api(Client):
        @route("users/{id}")
        def update_user(self, id, name: Query, trace: Header("X-Trace") = None): ...

    compiled = definition(Api, "update_user")
    assert compiled.http_method == "PUT"
    assert compiled.path.source == "/users/{id}"
    assert [tuple(b) for b in compiled.bindings] == [
        ("name", "query", "name"),
        ("trace", "header", "X-Trace"),
    ]


def test_explicit_method_wins():
    class Api(Client):
        @route("post", "/search")
        def search(self, body): ...

    assert definition(Api, "search").http_method == "POST"
    assert definition(Api, "search").body_param == "body"


def test_annotated_and_body_targets():
    class Api(Client):
        @route("/things")
        def create_thing(self, payload: Body, sort: Annotated[str | None, Query("s")] = None): ...

    compiled = definition(Api, "create_thing")
    assert compiled.body_param == "payload"
    assert compiled.bindings[0].key == "s"


def test_unused_parameter_fails_with_the_route_name():
    with pytest.raises(RouteDefinitionError, match=r"Api.get_user: parameter 'verbose'"):

        class Api(Client):
            @route("/users/{id}")
            def get_user(self, id, verbose): ...


def test_body_parameter_conflicts_with_a_body_template():
    with pytest.raises(RouteDefinitionError, match="body template"):

        class Api(Client):
            @route("/things", body={"a": "{a}"})
            def create_thing(self, a, extra: Body): ...


@pytest.mark.parametrize(
    ("args", "kwargs", "message"),
    [
        (("FETCH", "/x"), {}, "unknown HTTP method"),
        (("/x",), {"returns": "xml"}, "returns"),
        (("/x",), {"query": {"when": object()}}, "object values"),
    ],
)
def test_bad_options_fail_at_class_creation(args, kwargs, message):
    with pytest.raises(RouteDefinitionError, match=message):

        class Api(Client):
            @route(*args, **kwargs)
            def get_x(self): ...


def test_variadic_parameters_are_rejected():
    with pytest.raises(RouteDefinitionError, match=r"\*\*rest"):

        class Api(Client):
            @route("/x")
            def get_x(self, **rest): ...


def test_route_headers_with_placeholders(transport, recorder):
    class Api(Client):
        base_url = "https://x.test"
        headers = {"X-Class": "1"}
        tenant = "acme"

        @route("POST", "/soap", headers={"SOAPAction": "urn:{action}", "X-Tenant": "{tenant}"})
        def call(self, action, body): ...

    Api(transport=transport).call("GetWeather", body="<x/>")
    assert recorder.last.headers["SOAPAction"] == "urn:GetWeather"
    assert recorder.last.headers["X-Tenant"] == "acme"
    assert recorder.last.headers["X-Class"] == "1"


def test_route_body_format_overrides_the_class(transport, recorder):
    class Api(Client):
        base_url = "https://x.test"

        @route("POST", "/login", body_format="form")
        def login(self, body): ...

        @route("POST", "/things")
        def create(self, body): ...

    api = Api(transport=transport)
    api.login(body={"user": "a"})
    assert recorder.last.headers["Content-Type"] == "application/x-www-form-urlencoded"
    api.create(body={"user": "a"})
    assert recorder.last.headers["Content-Type"] == "application/json"


def test_unknown_route_body_format():
    with pytest.raises(RouteDefinitionError, match="body_format"):

        class Api(Client):
            @route("POST", "/x", body_format="xml")
            def create_x(self, body): ...
