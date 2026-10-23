import httpx

from apiroute import Client, Section, route


class Api(Client):
    base_url = "https://x.test"
    headers = {"X-A": "1"}

    @route("/things")
    def get_things(self): ...

    @route("/things", body={"name": "{name}", "tags": ["a"], "draft": True})
    def create_thing(self, name): ...

    class admin(Section):
        @route("/admin")
        def get(self): ...


def test_options_apply_to_routes_and_chain(transport, recorder):
    view = Api(transport=transport).with_options(headers={"X-B": "2"}, query={"q": "x"})
    view.with_options(headers={"X-A": None}).get_things()
    assert "X-A" not in recorder.last.headers
    assert recorder.last.headers["X-B"] == "2"
    assert recorder.last.url.params["q"] == "x"


def test_returns_option(transport, recorder):
    recorder.respond(httpx.Response(200, text="raw"))
    assert Api(transport=transport).with_options(returns="text").get_things() == "raw"


def test_options_reach_sections(transport, recorder):
    Api(transport=transport).with_options(query={"q": "1"}).admin.get()
    assert recorder.last.url.params["q"] == "1"


def test_other_attributes_pass_through(transport):
    client = Api(transport=transport)
    assert client.with_options(timeout=1).base_url == "https://x.test"


def test_does_not_change_the_client(transport, recorder):
    client = Api(transport=transport)
    client.with_options(headers={"X-B": "2"})
    client.get_things()
    assert "X-B" not in recorder.last.headers


def test_chained_bodies_merge_over_the_route_body(transport, recorder):
    view = Api(transport=transport).with_options(body={"tags": ["b"], "owner": "me"})
    view.with_options(body={"draft": None}).create_thing("x")
    assert recorder.last_json() == {"name": "x", "tags": ["b"], "owner": "me"}
