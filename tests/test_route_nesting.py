from apiroute import Client, Section, route
from apiroute.route_decorator import RouteDecorator
from apiroute.route_method import RouteMethod


class RecordingMethod(RouteMethod):
    def __init__(self, func, spec):
        super().__init__(func, spec)
        self.enclosing = []

    def nested_in(self, root):
        self.enclosing.append(root.__qualname__.rsplit("<locals>.", 1)[-1])


def recording(path):
    spec = route(path)._spec
    return lambda func: RecordingMethod(func, spec)


def test_section_routes_hear_from_each_enclosing_class_innermost_first():
    class Api(Client):
        class outer(Section):
            @recording("/a")
            def a(self): ...

            class inner(Section):
                @recording("/b")
                def b(self): ...

    assert vars(Api.outer)["a"].enclosing == ["Api"]
    assert vars(Api.outer.inner)["b"].enclosing == ["Api.outer", "Api"]


def test_client_routes_arent_nested():
    class Api(Client):
        @recording("/a")
        def a(self): ...

    assert vars(Api)["a"].enclosing == []


def test_plain_routes_ignore_the_hook():
    class Api(Client):
        class s(Section):
            get_x = route("/x")

    assert isinstance(vars(Api.s)["get_x"], RouteMethod)
    assert not isinstance(vars(Api.s)["get_x"], RouteDecorator)
