import httpx
import pytest

from apiroute import RequestSpec, UnexpectedResponse
from apiroute.auth.async_auth_attempts import AsyncAuthAttempts
from apiroute.auth.auth_attempts import AuthAttempts
from apiroute.auth.authenticator import Authenticator

REQUEST = RequestSpec("GET", "https://api.test/x", {}, [], None, None)


class Numbered(Authenticator):
    def __init__(self):
        self.current = 1
        self.invalidated = []

    def credential(self, client):
        return self.current

    def apply(self, request, credential):
        return credential

    def invalidate(self, credential):
        self.invalidated.append(credential)
        self.current += 1


def unauthorized():
    request = httpx.Request("GET", "https://api.test/x")
    return UnexpectedResponse("x", httpx.Response(401, request=request))


def attempts_failing(times, error_factory=unauthorized):
    sent = []

    def attempt(authorize):
        sent.append(authorize(REQUEST))
        if len(sent) <= times:
            raise error_factory()
        return "ok"

    return sent, attempt


def test_without_an_authenticator_the_request_is_unchanged():
    sent, attempt = attempts_failing(0)
    assert AuthAttempts(None, None, "x").run(attempt) == "ok"
    assert sent == [REQUEST]


def test_without_an_authenticator_a_401_is_raised():
    _, attempt = attempts_failing(1)
    with pytest.raises(UnexpectedResponse):
        AuthAttempts(None, None, "x").run(attempt)


def test_a_rejected_credential_is_invalidated_and_the_attempt_sent_once_more():
    auth = Numbered()
    sent, attempt = attempts_failing(1)
    assert AuthAttempts(auth, None, "x").run(attempt) == "ok"
    assert sent == [1, 2]
    assert auth.invalidated == [1]


def test_only_one_resend():
    auth = Numbered()
    sent, attempt = attempts_failing(2)
    with pytest.raises(UnexpectedResponse):
        AuthAttempts(auth, None, "x").run(attempt)
    assert sent == [1, 2]


def test_errors_that_dont_reject_the_credential_are_raised_as_they_are():
    auth = Numbered()
    sent, attempt = attempts_failing(1, lambda: httpx.ConnectError("x"))
    with pytest.raises(httpx.ConnectError):
        AuthAttempts(auth, None, "x").run(attempt)
    assert sent == [1]
    assert auth.invalidated == []


@pytest.mark.anyio
async def test_async_runs_the_same_way():
    auth = Numbered()
    sent, attempt = attempts_failing(1)

    async def async_attempt(authorize):
        return attempt(authorize)

    assert await AsyncAuthAttempts(auth, None, "x").run(async_attempt) == "ok"
    assert sent == [1, 2]


@pytest.mark.anyio
async def test_async_without_an_authenticator():
    async def attempt(authorize):
        return authorize(REQUEST)

    assert await AsyncAuthAttempts(None, None, "x").run(attempt) is REQUEST


@pytest.mark.anyio
async def test_async_only_one_resend_and_other_errors_raise():
    auth = Numbered()
    sent, attempt = attempts_failing(2)

    async def async_attempt(authorize):
        return attempt(authorize)

    with pytest.raises(UnexpectedResponse):
        await AsyncAuthAttempts(auth, None, "x").run(async_attempt)
    assert sent == [1, 2]

    _, failing = attempts_failing(1, lambda: ValueError("x"))

    async def other(authorize):
        return failing(authorize)

    with pytest.raises(ValueError):
        await AsyncAuthAttempts(Numbered(), None, "x").run(other)
