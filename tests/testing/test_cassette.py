import json

import httpx
import pytest

from apiroute import (
    AsyncHttpxClientTransport,
    Client,
    HttpxClientTransport,
    Retries,
    route,
)
from apiroute.testing import CassetteMismatch, cassette


class GitHub(Client):
    base_url = "https://api.test"
    headers = {"Authorization": "Bearer real-token"}
    retries = Retries(attempts=2, sleep=5)
    get_user = route("/users/{name}")
    search = route("/search", query={"q": "{q}", "api_key": "s3cret"})
    create = route("POST", "/repos")
    events = route("/events", stream="sse")


class Server:
    """The "real" API while recording: counts what reaches it."""

    def __init__(self):
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if request.url.path == "/events":
            return httpx.Response(200, content=b"data: a\n\ndata: b\n\n")
        if request.method == "POST":
            return httpx.Response(201, json=json.loads(request.content))
        return httpx.Response(200, json={"path": request.url.path, "n": len(self.requests)})


@pytest.fixture
def server():
    return Server()


@pytest.fixture
def real(server):
    return {
        "transport": HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(server))),
        "async_transport": AsyncHttpxClientTransport(
            httpx.AsyncClient(transport=httpx.MockTransport(server))
        ),
    }


def test_records_the_first_time_and_replays_after(tmp_path, server, real):
    path = tmp_path / "users.json"
    with cassette(path, **real):
        first = GitHub().get_user(name="octocat")
    assert path.exists() and len(server.requests) == 1
    with cassette(path, **real) as tape:
        assert GitHub().get_user(name="octocat") == first
    assert len(server.requests) == 1
    assert tape.unplayed == []


def test_the_file_keeps_no_credentials(tmp_path, real):
    path = tmp_path / "search.json"
    with cassette(path, **real):
        GitHub().search(q="apiroute")
    text = path.read_text()
    assert "real-token" not in text and "s3cret" not in text
    saved = json.loads(text)
    assert saved["version"] == 1
    assert saved["interactions"][0]["request"]["url"].startswith(
        "https://api.test/search?q=apiroute"
    )
    with cassette(path, mode="replay"):
        assert GitHub().search(q="apiroute")["path"] == "/search"


def test_replay_needs_the_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        with cassette(tmp_path / "missing.json", mode="replay"):
            pass


def test_a_request_not_recorded_fails(tmp_path, real):
    path = tmp_path / "users.json"
    with cassette(path, **real):
        GitHub().get_user(name="octocat")
    with cassette(path), pytest.raises(CassetteMismatch, match="GET https://api.test/users/other"):
        GitHub().get_user(name="other")


def test_each_recording_plays_once_in_order(tmp_path, real):
    path = tmp_path / "twice.json"
    with cassette(path, **real):
        GitHub().get_user(name="a"), GitHub().get_user(name="a")
    with cassette(path):
        assert [GitHub().get_user(name="a")["n"] for _ in range(2)] == [1, 2]
        with pytest.raises(CassetteMismatch):
            GitHub().get_user(name="a")


def test_bodies_are_matched_when_asked(tmp_path, real):
    path = tmp_path / "create.json"
    with cassette(path, match_body=True, **real):
        GitHub().create(body={"name": "one"})
        GitHub().create(body={"name": "two"})
    with cassette(path, match_body=True):
        assert GitHub().create(body={"name": "two"}) == {"name": "two"}
        with pytest.raises(CassetteMismatch):
            GitHub().create(body={"name": "three"})


def test_redact_scrubs_what_the_defaults_dont(tmp_path, real):
    def scrub(item):
        item["response"]["body"]["json"]["path"] = "[path]"
        return item

    path = tmp_path / "scrubbed.json"
    with cassette(path, redact=scrub, **real):
        GitHub().get_user(name="octocat")
    assert "/users/octocat" not in json.dumps(
        json.loads(path.read_text())["interactions"][0]["response"]
    )
    with cassette(path):
        assert GitHub().get_user(name="octocat")["path"] == "[path]"


def test_a_failing_block_saves_nothing(tmp_path, real):
    path = tmp_path / "failed.json"
    with pytest.raises(RuntimeError):
        with cassette(path, **real):
            GitHub().get_user(name="a")
            raise RuntimeError("test failed")
    assert not path.exists()


def test_record_mode_replaces_the_file(tmp_path, server, real):
    path = tmp_path / "users.json"
    with cassette(path, **real):
        GitHub().get_user(name="a")
    with cassette(path, mode="record", **real):
        GitHub().get_user(name="b")
    assert len(server.requests) == 2
    with cassette(path), pytest.raises(CassetteMismatch):
        GitHub().get_user(name="a")


def test_streams_are_recorded_whole_and_replayed(tmp_path, real):
    path = tmp_path / "events.json"
    with cassette(path, **real):
        assert [e.data for e in GitHub().events()] == ["a", "b"]
    with cassette(path):
        assert [e.data for e in GitHub().events()] == ["a", "b"]


def test_assert_all_played(tmp_path, real):
    path = tmp_path / "users.json"
    with cassette(path, **real):
        GitHub().get_user(name="a"), GitHub().get_user(name="b")
    with pytest.raises(AssertionError, match="1 recordings were never replayed"):
        with cassette(path, assert_all_played=True):
            GitHub().get_user(name="a")


def test_retries_during_replay_dont_wait(tmp_path):
    path = tmp_path / "flaky.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "interactions": [
                    {
                        "request": {
                            "method": "GET",
                            "url": "https://api.test/users/a",
                            "headers": [],
                            "body": {},
                        },
                        "response": {"status": 503, "headers": [], "body": {}},
                    }
                ],
            }
        )
    )

    class Retrying(GitHub):
        def should_retry(self, error, attempt):
            return True

    with cassette(path) as tape, pytest.raises(CassetteMismatch):
        Retrying().get_user(name="a")
    assert tape.unplayed == []


def test_not_a_cassette(tmp_path):
    path = tmp_path / "other.json"
    path.write_text('{"version": 9, "interactions": []}')
    with pytest.raises(ValueError, match="not a version 1 apiroute cassette"):
        with cassette(path):
            pass


def test_unknown_modes_fail(tmp_path):
    with pytest.raises(ValueError, match="mode must be one of"):
        with cassette(tmp_path / "x.json", mode="sometimes"):
            pass


@pytest.mark.anyio
async def test_async_record_and_replay(tmp_path, server, real):
    path = tmp_path / "async.json"
    with cassette(path, **real):
        recorded = await GitHub().aio.get_user(name="a")
        events = await GitHub().aio.events()
        assert [e.data async for e in events] == ["a", "b"]
    with cassette(path):
        assert await GitHub().aio.get_user(name="a") == recorded
        events = await GitHub().aio.events()
        assert [e.data async for e in events] == ["a", "b"]
    assert len(server.requests) == 2


def test_empty_bodies_replay_empty(tmp_path, real, server):
    class Deleting(GitHub):
        remove = route("DELETE", "/repos/{name}", expected=204)

    def no_content(request):
        return httpx.Response(204)

    transport = HttpxClientTransport(httpx.Client(transport=httpx.MockTransport(no_content)))
    path = tmp_path / "delete.json"
    with cassette(path, transport=transport):
        assert Deleting().remove(name="x") is None
    with cassette(path):
        assert Deleting().remove(name="x") is None


@pytest.mark.anyio
async def test_recording_transports_close_what_they_wrap():
    from apiroute.testing.async_recording_transport import AsyncRecordingTransport
    from apiroute.testing.recording_transport import RecordingTransport

    closed = []

    class Inner:
        def close(self):
            closed.append("sync")

        async def aclose(self):
            closed.append("async")

    RecordingTransport(Inner(), print).close()
    await AsyncRecordingTransport(Inner(), print).aclose()
    assert closed == ["sync", "async"]
