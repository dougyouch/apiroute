import json
from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import pytest

from apiroute import Client, Retries, RouteDefinitionError, UnexpectedResponse, route
from apiroute.streaming import EventIterator, ServerSentEvent
from apiroute.testing import MockTransport
from apiroute.testing.sleep_recording import recorded_sleeps


@dataclass
class Row:
    n: int


class Api(Client):
    base_url = "https://x.test"
    retries = Retries(attempts=3, sleep=0.25)

    @route("/log", stream="lines")
    def tail(self): ...

    @route("/rows", stream="ndjson")
    def rows(self): ...

    @route("/rows", stream="ndjson")
    def typed_rows(self) -> Iterator[Row]: ...

    @route("/rows", stream="ndjson", model=Row)
    def model_rows(self): ...

    @route("/events", query={"topic": "{topic}"}, stream="sse")
    def events(self, topic: str | None = None): ...

    @route("POST", "/completions", stream="sse")
    def complete(self, body: dict): ...

    @route("POST", "/watch", stream="sse", idempotent=True)
    def watch(self, body: dict): ...


class OneAttempt(Api):
    retries = Retries()


@pytest.fixture
def api(transport):
    return Api(transport=transport)


def body(*chunks, then=None):
    """A streamed response body: the chunks, then the exception `then` raised mid-body."""

    def stream():
        yield from chunks
        if then is not None:
            raise then

    return httpx.Response(200, content=stream())


def sse(*chunks, then=None):
    response = body(*chunks, then=then)
    response.headers["Content-Type"] = "text/event-stream"
    return response


def test_lines_yields_each_line_as_it_arrives(api, recorder):
    recorder.respond(body(b"one\ntw", b"o\r\nthree"))
    lines = api.tail()
    assert isinstance(lines, EventIterator)
    assert list(lines) == ["one", "two", "three"]
    assert lines.response.is_closed


def test_lines_decode_with_the_declared_charset(api, recorder):
    recorder.respond(
        httpx.Response(
            200,
            content="é\n".encode("latin-1"),
            headers={"Content-Type": "text/plain; charset=latin-1"},
        )
    )
    assert list(api.tail()) == ["é"]


def test_ndjson_yields_json_values(api, recorder):
    recorder.respond(body(b'{"n": 1}\n\n{"n"', b": 2}\n[3]"))
    assert list(api.rows()) == [{"n": 1}, {"n": 2}, [3]]


def test_ndjson_converts_items_by_the_return_annotation(api, recorder):
    recorder.respond(body(b'{"n": 1}\n{"n": 2}\n'))
    assert list(api.typed_rows()) == [Row(1), Row(2)]


def test_ndjson_converts_items_by_model(api, recorder):
    recorder.respond(body(b'{"n": 1}\n'))
    assert list(api.model_rows()) == [Row(1)]


def test_ndjson_raises_on_a_line_that_isnt_json_and_closes(api, recorder):
    recorder.respond(body(b'{"n": 1}\nnope\n'))
    rows = api.rows()
    assert next(rows) == {"n": 1}
    with pytest.raises(json.JSONDecodeError):
        next(rows)
    assert rows.response.is_closed


def test_sse_yields_events(api, recorder):
    recorder.respond(sse(b'event: delta\ndata: {"t": 1}\n\n: ping\n\ndata: done\n\n'))
    events = list(api.events())
    assert events == [ServerSentEvent('{"t": 1}', "delta"), ServerSentEvent("done")]
    assert events[0].json() == {"t": 1}


def test_items_arrive_before_the_body_ends(api, recorder):
    pulled = []

    def stream():
        for chunk in (b"data: 1\n\n", b"data: 2\n\n"):
            pulled.append(chunk)
            yield chunk

    recorder.respond(httpx.Response(200, content=stream()))
    events = api.events()
    assert next(events).data == "1"
    assert pulled == [b"data: 1\n\n"]
    events.close()


def test_leaving_a_with_block_early_closes_the_stream(api, recorder):
    recorder.respond(sse(b"data: 1\n\ndata: 2\n\n"))
    with api.events() as events:
        assert next(events).data == "1"
    assert events.response.is_closed


def test_an_error_status_raises_before_iterating_with_the_body_readable(api, recorder):
    recorder.respond(httpx.Response(403, content=b"forbidden"))
    with pytest.raises(UnexpectedResponse) as raised:
        api.events()
    assert raised.value.response.text == "forbidden"


def test_opening_the_stream_is_retried(api, recorder):
    recorder.respond(httpx.ConnectError("refused"), sse(b"data: ok\n\n"))
    with recorded_sleeps():
        assert [e.data for e in api.events()] == ["ok"]
    assert len(recorder.requests) == 2


def test_sse_reconnects_mid_body_with_the_last_event_id(api, recorder):
    recorder.respond(
        sse(
            b"id: 1\ndata: a\n\nid: 2\ndata: b\n\nid: 3\ndata: parti", then=httpx.ReadError("reset")
        ),
        sse(b"id: 3\ndata: c\n\n"),
    )
    with recorded_sleeps() as sleeps:
        events = list(api.events(topic="x"))
    assert [(e.id, e.data) for e in events] == [("1", "a"), ("2", "b"), ("3", "c")]
    assert sleeps == [0.25]
    first, second = recorder.requests
    assert "last-event-id" not in first.headers
    assert second.headers["Last-Event-ID"] == "2"
    assert second.url == first.url == "https://x.test/events?topic=x"


def test_sse_reconnects_without_a_header_when_no_id_was_sent(api, recorder):
    recorder.respond(sse(b"data: a\n\n", then=httpx.ReadError("reset")), sse(b"data: b\n\n"))
    with recorded_sleeps():
        assert [e.data for e in api.events()] == ["a", "b"]
    assert "last-event-id" not in recorder.last.headers


def test_sse_waits_the_servers_retry_time(api, recorder):
    recorder.respond(sse(b"retry: 5000\ndata: a\n\n", then=httpx.ReadError("x")), sse(b""))
    with recorded_sleeps() as sleeps:
        list(api.events())
    assert sleeps == [5.0]


def test_sse_gives_up_after_the_retries_run_out(api, recorder):
    recorder.respond(
        sse(b"data: a\n\n", then=httpx.ReadError("1")),
        sse(b"", then=httpx.ReadError("2")),
        sse(b"", then=httpx.ReadError("3")),
    )
    events = api.events()
    with recorded_sleeps(), pytest.raises(httpx.ReadError, match="3"):
        list(events)
    assert len(recorder.requests) == 3
    assert events.response.is_closed


def test_sse_failures_count_again_from_one_after_an_event(api, recorder):
    recorder.respond(
        sse(b"data: a\n\n", then=httpx.ReadError("1")),
        sse(b"", then=httpx.ReadError("2")),
        sse(b"data: b\n\n", then=httpx.ReadError("3")),
        sse(b"", then=httpx.ReadError("4")),
        sse(b"data: c\n\n"),
    )
    with recorded_sleeps():
        assert [e.data for e in api.events()] == ["a", "b", "c"]
    assert len(recorder.requests) == 5


def test_sse_doesnt_reconnect_without_retries(recorder, transport):
    recorder.respond(sse(b"data: a\n\n", then=httpx.ReadError("reset")))
    events = OneAttempt(transport=transport).events()
    assert next(events).data == "a"
    with pytest.raises(httpx.ReadError):
        next(events)
    assert len(recorder.requests) == 1


def test_sse_doesnt_reconnect_a_route_that_isnt_idempotent(api, recorder):
    recorder.respond(sse(b"data: a\n\n", then=httpx.ReadError("reset")))
    with pytest.raises(httpx.ReadError):
        list(api.complete({"prompt": "hi"}))
    assert len(recorder.requests) == 1


def test_sse_reconnects_an_idempotent_post_with_the_same_body(api, recorder):
    recorder.respond(sse(b"id: 1\ndata: a\n\n", then=httpx.ReadError("x")), sse(b"data: b\n\n"))
    with recorded_sleeps():
        assert [e.data for e in api.watch({"q": 1})] == ["a", "b"]
    assert [r.content for r in recorder.requests] == [b'{"q": 1}', b'{"q": 1}']


def test_sse_doesnt_reconnect_errors_should_retry_refuses(api, recorder):
    recorder.respond(sse(b"data: a\n\n", then=ValueError("broken")))
    with pytest.raises(ValueError):
        list(api.events())
    assert len(recorder.requests) == 1


def test_a_204_on_reconnect_ends_the_stream(api, recorder):
    recorder.respond(sse(b"data: a\n\n", then=httpx.ReadError("x")), httpx.Response(204))
    with recorded_sleeps():
        assert [e.data for e in api.events()] == ["a"]


def test_an_error_reopening_the_stream_is_raised(api, recorder):
    recorder.respond(sse(b"data: a\n\n", then=httpx.ReadError("x")), httpx.Response(500))
    with recorded_sleeps(), pytest.raises(UnexpectedResponse):
        list(api.events())


def test_a_204_at_first_is_an_empty_stream(api, recorder):
    recorder.respond(httpx.Response(204))
    assert list(api.events()) == []


def test_lines_and_ndjson_dont_reconnect(api, recorder):
    recorder.respond(body(b"a\n", then=httpx.ReadError("x")))
    lines = api.tail()
    assert next(lines) == "a"
    with pytest.raises(httpx.ReadError):
        next(lines)
    assert len(recorder.requests) == 1


def test_hooks_see_each_reconnect(recorder, transport):
    seen = []

    class Hooked(Api):
        def on_request(self, request):
            seen.append(request.headers.get("Last-Event-ID"))

    recorder.respond(sse(b"id: 4\ndata: a\n\n", then=httpx.ReadError("x")), sse(b""))
    with recorded_sleeps():
        list(Hooked(transport=transport).events())
    assert seen == [None, "4"]


def test_works_with_the_mock_transport():
    mock = MockTransport()
    mock.on(path="/events").respond(sse(b"data: hi\n\n"))
    assert [e.data for e in Api(transport=mock).events()] == ["hi"]


def test_generated_routes_take_no_destination(recorder, transport):
    class Generated(Client):
        base_url = "https://x.test"
        feed = route("/feed", stream="ndjson")

    recorder.respond(body(b"1\n2\n"))
    assert list(Generated(transport=transport).feed()) == [1, 2]


def test_ndjson_cant_take_another_returns():
    with pytest.raises(RouteDefinitionError, match="ndjson"):

        class Bad(Client):
            feed = route("/feed", stream="ndjson", returns="text")


def test_model_is_refused_for_other_event_streams():
    with pytest.raises(RouteDefinitionError, match="model="):

        class Bad(Client):
            feed = route("/feed", stream="sse", model=Row)


def test_check_is_refused_for_event_streams():
    with pytest.raises(RouteDefinitionError, match="check="):

        class Bad(Client):
            feed = route("/feed", stream="lines", check=lambda response: True)


def test_the_readme_example_an_annotated_sse_route_without_a_timeout(recorder, transport):
    class Llm(Client):
        base_url = "https://x.test"
        timeout = None

        @route("POST", "/v1/chat", stream="sse")
        def chat(self, body: dict) -> Iterator[ServerSentEvent]: ...

    recorder.respond(sse(b'data: {"delta": "Hi"}\n\ndata: [DONE]\n\n'))
    deltas = []
    with Llm(transport=transport).chat({"messages": []}) as events:
        for event in events:
            if event.data == "[DONE]":
                break
            deltas.append(event.json()["delta"])
    assert deltas == ["Hi"]
    assert events.response.is_closed
