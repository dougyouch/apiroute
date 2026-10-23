from apiroute import Client, Query, Section, route


class Api(Client):
    base_url = "https://x.test"
    headers = {"Authorization": lambda self: f"Bearer {self.token}"}
    token = "t"
    org = "acme"

    class issues(Section):
        inherit = ("headers",)
        headers = {"X-Section": "issues"}

        @route("/orgs/{org}/issues")
        def list(self, state: Query = None): ...

    class uploads(Section):
        base_url = "https://uploads.x.test"

        @route("POST", "/files")
        def create(self, body): ...

        class parts(Section):
            @route("/parts/{id}")
            def get(self, id): ...


def test_section_inherits_headers_and_resolves_against_root(transport, recorder):
    Api(transport=transport).issues.list(state="open")
    request = recorder.last
    assert str(request.url) == "https://x.test/orgs/acme/issues?state=open"
    assert request.headers["Authorization"] == "Bearer t"
    assert request.headers["X-Section"] == "issues"


def test_section_without_inherit_gets_no_root_headers(transport, recorder):
    Api(transport=transport).uploads.create(body={"a": 1})
    assert str(recorder.last.url) == "https://uploads.x.test/files"
    assert "Authorization" not in recorder.last.headers


def test_nested_section_uses_its_parents_base_url(transport, recorder):
    Api(transport=transport).uploads.parts.get(5)
    assert str(recorder.last.url) == "https://uploads.x.test/parts/5"


def test_section_is_cached_and_the_class_stays_reachable(transport):
    client = Api(transport=transport)
    assert client.issues is client.issues
    assert issubclass(Api.issues, Section)


def test_subclass_of_the_client_keeps_its_sections(transport, recorder):
    class Child(Api):
        token = "child"

    Child(transport=transport).issues.list()
    assert recorder.last.headers["Authorization"] == "Bearer child"
