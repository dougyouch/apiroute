import httpx
import pytest

from apiroute import UnexpectedResponse
from apiroute.response_reader import ResponseReader

REQUEST = httpx.Request("GET", "https://x.test/things")


def response(status=200, **kwargs):
    return httpx.Response(status, request=REQUEST, **kwargs)


@pytest.mark.parametrize(
    ("returns", "expected"),
    [("json", {"a": 1}), ("text", '{"a": 1}'), ("bytes", b'{"a": 1}')],
)
def test_return_modes(returns, expected):
    assert ResponseReader("r", None, returns).read(response(content=b'{"a": 1}')) == expected


def test_response_mode_returns_the_response():
    raw = response()
    assert ResponseReader("r", None, "response").read(raw) is raw


def test_empty_json_body_is_none():
    assert ResponseReader("r", None, "json").read(response(204)) is None


def test_non_2xx_raises_with_context():
    with pytest.raises(UnexpectedResponse, match="get_thing: unexpected status 404") as raised:
        ResponseReader("get_thing", None, "json").read(response(404))
    assert raised.value.status_code == 404
    assert raised.value.response.request is REQUEST


def test_expected_codes_replace_the_2xx_rule():
    reader = ResponseReader("r", frozenset({202}), "text")
    assert reader.read(response(202, text="queued")) == "queued"
    with pytest.raises(UnexpectedResponse):
        reader.read(response(200))


def test_invalid_json_raises_unexpected_response():
    with pytest.raises(UnexpectedResponse, match="get_thing: invalid JSON body from GET"):
        ResponseReader("get_thing", None, "json").read(response(content=b"<html>"))
