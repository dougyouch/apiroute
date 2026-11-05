from collections.abc import Iterator
from dataclasses import dataclass

import httpx
import pytest

from apiroute import Client, Retries, UnexpectedResponse, route
from apiroute.streaming import AsyncEventIterator, ServerSentEvent
from apiroute.testing.sleep_recording import recorded_sleeps

pytestmark = pytest.mark.anyio


@dataclass
class Row:
    n: int


class Api(Client):
    base_url = "https://x.test"
    retries = Retries(attempts=3, sleep=0.25)

    tail = route("/log", stream="lines")
    events = route("/events", stream="sse")
    complete = route("POST", "/completions", stream="sse")

    @route("/rows", stream="ndjson")
    def rows(self) -> Iterator[Row]: ...


@pytest.fixture
def api(async_transport):
    return Api(async_transport=async_transport)


def body(*chunks, then=None):
    async def stream():
        for chunk in chunks:
            yield chunk
        if then is not None:
            raise then

    return httpx.Response(200, content=stream())


async def collect(iterator):
    return [item async for item in iterator]


async def test_lines(api, recorder):
    recorder.respond(body(b"a\r", b"\nb\n"))
    lines = await api.aio.tail()
    assert isinstance(lines, AsyncEventIterator)
    assert await collect(lines) == ["a", "b"]
    assert lines.response.is_closed


async def test_ndjson_converts_items(api, recorder):
    recorder.respond(body(b'{"n": 1}\n{"n": 2}'))
    assert await collect(await api.aio.rows()) == [Row(1), Row(2)]


async def test_sse(api, recorder):
    recorder.respond(body(b"event: x\nid: 1\ndata: a\n\n"))
    assert await collect(await api.aio.events()) == [ServerSentEvent("a", "x", "1")]


async def test_async_with_closes_early(api, recorder):
    recorder.respond(body(b"data: 1\n\ndata: 2\n\n"))
    async with await api.aio.events() as events:
        assert (await events.__anext__()).data == "1"
    assert events.response.is_closed


async def test_an_error_status_raises(api, recorder):
    recorder.respond(httpx.Response(500, content=b"boom"))
    with pytest.raises(UnexpectedResponse) as raised:
        await api.aio.events()
    assert raised.value.response.text == "boom"


async def test_sse_reconnects_with_the_last_event_id(api, recorder):
    recorder.respond(
        body(b"id: 1\ndata: a\n\nretry: 2000\n", then=httpx.ReadError("x")),
        body(b"data: b\n\n"),
    )
    with recorded_sleeps() as sleeps:
        events = await collect(await api.aio.events())
    assert [e.data for e in events] == ["a", "b"]
    assert sleeps == [2.0]
    assert recorder.last.headers["Last-Event-ID"] == "1"


async def test_sse_gives_up_after_the_retries_run_out(api, recorder):
    recorder.respond(*[body(b"", then=httpx.ReadError(str(n))) for n in range(3)])
    events = await api.aio.events()
    with recorded_sleeps(), pytest.raises(httpx.ReadError, match="2"):
        await collect(events)
    assert len(recorder.requests) == 3
    assert events.response.is_closed


async def test_sse_doesnt_reconnect_a_post(api, recorder):
    recorder.respond(body(b"data: a\n\n", then=httpx.ReadError("x")))
    with pytest.raises(httpx.ReadError):
        await collect(await api.aio.complete())
    assert len(recorder.requests) == 1


async def test_a_204_on_reconnect_ends_the_stream(api, recorder):
    recorder.respond(body(b"data: a\n\n", then=httpx.ReadError("x")), httpx.Response(204))
    with recorded_sleeps():
        assert [e.data for e in await collect(await api.aio.events())] == ["a"]


async def test_lines_dont_reconnect(api, recorder):
    recorder.respond(body(b"a\n", then=httpx.ReadError("x")))
    with pytest.raises(httpx.ReadError):
        await collect(await api.aio.tail())
    assert len(recorder.requests) == 1
