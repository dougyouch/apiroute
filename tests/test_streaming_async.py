import httpx
import pytest

from apiroute import Client, UnexpectedResponse, route
from apiroute.async_chunk_iterator import AsyncChunkIterator

pytestmark = pytest.mark.anyio


class Api(Client):
    base_url = "https://x.test"

    download = route("/files/{id}", stream="file")
    copy_to = route("/files/{id}", stream="io")
    get_events = route("/events", stream="iter")


@pytest.fixture
def api(async_transport):
    return Api(async_transport=async_transport)


async def test_file_mode(api, recorder, tmp_path):
    recorder.respond(httpx.Response(200, content=b"abcd"))
    target = tmp_path / "out.bin"
    await api.aio.download(id=1, file=str(target))
    assert target.read_bytes() == b"abcd"


async def test_error_leaves_no_file(api, recorder, tmp_path):
    recorder.respond(httpx.Response(500, content=b"boom"))
    target = tmp_path / "out.bin"
    with pytest.raises(UnexpectedResponse) as raised:
        await api.aio.download(id=1, file=str(target))
    assert raised.value.response.text == "boom"
    assert not target.exists()


async def test_io_mode_awaits_async_writers(api, recorder):
    written = []

    class AsyncWriter:
        async def write(self, chunk):
            written.append(chunk)

    recorder.respond(httpx.Response(200, content=b"abcd"))
    await api.aio.copy_to(id=1, io=AsyncWriter())
    assert b"".join(written) == b"abcd"


async def test_iter_mode(api, recorder):
    recorder.respond(httpx.Response(200, content=b"abc"))
    events = await api.aio.get_events()
    assert isinstance(events, AsyncChunkIterator)
    async with events:
        assert b"".join([chunk async for chunk in events]) == b"abc"
    assert events.response.is_closed
