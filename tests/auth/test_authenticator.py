import dataclasses

import httpx
import pytest

from apiroute import Client, HttpxClientTransport, UnexpectedResponse, route
from apiroute.auth import Authenticator


class SessionExpired(Exception):
    pass


class SessionAuth(Authenticator):
    """A login-session API: a session ID in a header, renewed when the API says it expired
    (with a 200 whose body says so)."""

    def __init__(self):
        self.logins = 0
        self.session = None

    def credential(self, client):
        if self.session is None:
            self.logins += 1
            self.session = f"s{self.logins}"
        return self.session

    def apply(self, request, credential):
        return dataclasses.replace(request, headers={**request.headers, "X-Session": credential})

    def rejects(self, error):
        return isinstance(error, SessionExpired)

    def invalidate(self, credential):
        if self.session == credential:
            self.session = None


class Api(Client):
    base_url = "https://api.test"
    get_x = route("/x")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.authenticator = SessionAuth()

    def check_response(self, request, response):
        if response.json().get("error") == "session_expired":
            raise SessionExpired()


def transport_for(handler):
    return HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(handler)))


def test_a_custom_authenticator_with_its_own_rejection():
    live = {"s2"}
    sessions = []

    def handler(request):
        sessions.append(request.headers["X-Session"])
        if request.headers["X-Session"] in live:
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(200, json={"error": "session_expired"})

    api = Api(transport=transport_for(handler))
    assert api.get_x() == {"ok": True}
    assert sessions == ["s1", "s2"]
    assert api.authenticator.logins == 2


def test_a_custom_rejects_replaces_the_401_rule():
    statuses = iter([401])

    def handler(request):
        return httpx.Response(next(statuses), json={})

    api = Api(transport=transport_for(handler))
    with pytest.raises(UnexpectedResponse):
        api.get_x()
    assert api.authenticator.logins == 1


def test_the_base_class_methods():
    auth = Authenticator()
    with pytest.raises(NotImplementedError):
        auth.credential(None)
    with pytest.raises(NotImplementedError):
        auth.apply(None, None)
    assert auth.invalidate("x") is None


def test_rejects_a_401_by_default():
    request = httpx.Request("GET", "https://api.test/x")
    rejected = UnexpectedResponse("r", httpx.Response(401, request=request))
    other = UnexpectedResponse("r", httpx.Response(403, request=request))
    assert Authenticator().rejects(rejected)
    assert not Authenticator().rejects(other)
    assert not Authenticator().rejects(ValueError())


@pytest.mark.anyio
async def test_acredential_calls_credential_by_default():
    class Fixed(Authenticator):
        def credential(self, client):
            return "c"

    assert await Fixed().acredential(None) == "c"


def test_an_authenticator_set_on_the_class_is_shared():
    class Shared(Client):
        base_url = "https://api.test"
        authenticator = SessionAuth()
        get_x = route("/x")

    def handler(request):
        return httpx.Response(200, json={"session": request.headers["X-Session"]})

    first = Shared(transport=transport_for(handler))
    second = Shared(transport=transport_for(handler))
    assert first.get_x() == second.get_x() == {"session": "s1"}
