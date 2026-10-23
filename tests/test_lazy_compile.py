import inspect

import pytest

from apiroute import Client, RouteDefinitionError, Section, route


def test_lazy_routes_compile_on_first_use(transport, recorder):
    class Api(Client):
        base_url = "https://x.test"
        compile_routes = "lazy"

        @route("/users/{id}")
        def get_user(self, id): ...

    assert vars(Api)["get_user"]._definition is None
    Api(transport=transport).get_user(1)
    assert str(recorder.last.url) == "https://x.test/users/1"
    assert vars(Api)["get_user"]._definition is not None


def test_lazy_route_errors_surface_on_first_use():
    class Api(Client):
        compile_routes = "lazy"

        @route("/users")
        def get_users(self, unused): ...

    with pytest.raises(RouteDefinitionError, match="unused"):
        Api().get_users()


def test_signatures_still_work_before_any_call():
    class Api(Client):
        compile_routes = "lazy"

        @route("/users/{id}")
        def get_user(self, id: int) -> dict: ...

    assert str(inspect.signature(Api.get_user)) == "(self, id: int) -> dict"


def test_eager_is_the_default_and_sections_choose_their_own():
    with pytest.raises(RouteDefinitionError):

        class Api(Client):
            @route("/x")
            def get_x(self, unused): ...

    class Lazy(Client):
        compile_routes = "lazy"

        class things(Section):
            @route("/things")
            def list(self): ...

    assert vars(Lazy.things)["list"]._definition is not None


def test_invalid_setting():
    with pytest.raises(ValueError, match="compile_routes"):

        class Api(Client):
            compile_routes = "sometimes"
