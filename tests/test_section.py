import httpx
import pytest

from apiroute import Client, Query, Retries, Section, UnexpectedResponse, route


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


class PolicyApi(Client):
    base_url = "https://x.test"
    retries = Retries(attempts=3, sleep=0)
    timeout = 7

    def should_retry(self, error, attempt):
        return isinstance(error, UnexpectedResponse) and error.status_code == 503

    class inheriting(Section):
        inherit = ("retries", "timeout")
        get = route("/a")

    class own(Section):
        inherit = ("retries", "timeout")
        retries = Retries(attempts=1)
        get = route("/b")

    class plain(Section):
        get = route("/c")


def _answers(recorder, count):
    recorder.respond(*[httpx.Response(503)] * count, httpx.Response(200, json={}))


def test_a_section_inheriting_retries_and_timeout_uses_the_root_clients(transport, recorder):
    api = PolicyApi(transport=transport)
    _answers(recorder, 2)
    api.inheriting.get()
    assert len(recorder.requests) == 3
    assert api.inheriting._request_config().timeout == 7


def test_a_root_subclass_policy_reaches_inheriting_sections(transport, recorder):
    class Stricter(PolicyApi):
        retries = Retries(attempts=1)

    _answers(recorder, 1)
    with pytest.raises(UnexpectedResponse):
        Stricter(transport=transport).inheriting.get()


def test_a_section_setting_its_own_keeps_it_and_one_not_inheriting_gets_the_defaults(
    transport, recorder
):
    api = PolicyApi(transport=transport)
    _answers(recorder, 1)
    with pytest.raises(UnexpectedResponse):
        api.own.get()
    assert api.own._request_config().timeout == 7
    assert api.plain._request_config().retries == Retries()
    assert api.plain._request_config().timeout == 30.0


def test_inherit_still_rejects_other_settings():
    with pytest.raises(ValueError, match="inherit may only list"):

        class Bad(Section):
            inherit = ("base_url",)


class MovedApi(Client):
    base_url = "https://old.x.test"
    follow_redirects = True

    get = route("/a")

    class nested(Section):
        get = route("/b")

    class stays(Section):
        follow_redirects = False
        get = route("/c")


def test_follow_redirects_is_sent_with_each_request_and_sections_take_their_parents():
    api = MovedApi()
    assert api._request_config().follow_redirects is True
    assert api.nested._request_config().follow_redirects is True
    assert api.stays._request_config().follow_redirects is False
    assert Api()._request_config().follow_redirects is None


def test_a_redirect_is_followed_only_when_the_client_asks(transport, recorder):
    moved = httpx.Response(302, headers={"Location": "https://new.x.test/a"})
    recorder.respond(moved, httpx.Response(200, json={"moved": True}))
    assert MovedApi(transport=transport).get() == {"moved": True}
    assert [str(r.url) for r in recorder.requests] == [
        "https://old.x.test/a",
        "https://new.x.test/a",
    ]

    recorder.respond(moved)
    with pytest.raises(UnexpectedResponse, match="unexpected status 302"):
        MovedApi(transport=transport).stays.get()
