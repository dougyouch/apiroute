import httpx
import pytest

from apiroute.testing.interaction import REDACTED, Interaction


def exchange(
    url="https://api.test/users?page=2&api_key=s3cret",
    request_headers=None,
    content=b"",
    status=200,
    response_headers=None,
    body=b'{"ok": true}',
):
    request = httpx.Request("POST", url, headers=request_headers or {}, content=content)
    response = httpx.Response(status, headers=response_headers or {}, content=body, request=request)
    return request, response


def test_credentials_in_headers_and_query_are_redacted():
    request, response = exchange(
        request_headers={
            "Authorization": "Bearer t",
            "Cookie": "s=1",
            "X-Api-Key": "k",
            "X-Session-Id": "abc",
            "Accept": "application/json",
        },
        response_headers={"Set-Cookie": "s=2", "X-Request-Id": "r1"},
    )
    interaction = Interaction.recorded(request, response)
    headers = dict(interaction.request_headers)
    assert headers["authorization"] == headers["cookie"] == headers["x-api-key"] == REDACTED
    assert headers["x-session-id"] == REDACTED
    assert headers["accept"] == "application/json"
    assert dict(interaction.response_headers) == {"set-cookie": REDACTED, "x-request-id": "r1"}
    assert "s3cret" not in interaction.url
    assert "page=2" in interaction.url


def test_wire_headers_are_dropped_since_the_body_is_kept_decoded():
    request, response = exchange(
        response_headers={"Content-Length": "12", "Content-Encoding": "identity"}
    )
    assert Interaction.recorded(request, response).response_headers == ()


@pytest.mark.parametrize(
    ("content", "kept"),
    [
        (b'{"a": [1, 2]}', {"json": {"a": [1, 2]}}),
        (b"[1]", {"json": [1]}),
        (b"plain words", {"text": "plain words"}),
        (b"{not json", {"text": "{not json"}),
        (b"\xff\x00", {"base64": "/wA="}),
        (b"", {}),
    ],
)
def test_bodies_are_kept_readably(content, kept):
    request, response = exchange(content=content, body=content)
    interaction = Interaction.recorded(request, response)
    assert interaction.request_body == interaction.response_body == kept


def test_json_round_trip_and_replayed_response():
    request, response = exchange(status=201, response_headers={"Content-Type": "application/json"})
    interaction = Interaction.from_json(Interaction.recorded(request, response).to_json())
    replayed = interaction.response(request)
    assert (replayed.status_code, replayed.json()) == (201, {"ok": True})
    assert replayed.headers["content-type"] == "application/json"
    assert replayed.request is request


def test_a_live_request_matches_by_method_and_redacted_url():
    request, response = exchange()
    interaction = Interaction.recorded(request, response)
    assert interaction.matches(httpx.Request("POST", str(request.url)), match_body=False)
    other_secret = "https://api.test/users?page=2&api_key=different"
    assert interaction.matches(httpx.Request("POST", other_secret), match_body=False)
    assert not interaction.matches(httpx.Request("GET", str(request.url)), match_body=False)
    assert not interaction.matches(
        httpx.Request("POST", "https://api.test/users?page=3"), match_body=False
    )


def test_bodies_match_when_asked():
    request, response = exchange(content=b'{"a": 1, "b": 2}')
    interaction = Interaction.recorded(request, response)
    assert interaction.matches(httpx.Request("POST", request.url, content=b'{"b":2,"a":1}'), True)
    assert not interaction.matches(httpx.Request("POST", request.url, content=b'{"a": 2}'), True)
    assert not interaction.matches(httpx.Request("POST", request.url, content=b"not json"), True)
    assert interaction.matches(httpx.Request("POST", request.url, content=b"anything"), False)


def test_text_bodies_match_exactly():
    request, response = exchange(content=b"a=1&b=2")
    interaction = Interaction.recorded(request, response)
    assert interaction.matches(httpx.Request("POST", request.url, content=b"a=1&b=2"), True)
    assert not interaction.matches(httpx.Request("POST", request.url, content=b"a=1"), True)
