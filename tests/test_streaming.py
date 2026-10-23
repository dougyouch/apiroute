import io

import httpx
import pytest

from apiroute import Client, Retries, RouteDefinitionError, UnexpectedResponse, route
from apiroute.chunk_iterator import ChunkIterator


class Api(Client):
    base_url = "https://x.test"
    retries = Retries(attempts=2, sleep=0)

    @route("/files/{id}", stream="file")
    def download(self, id: int, file: str): ...

    @route("/files/{id}", stream="io")
    def copy_to(self, id: int, io): ...

    @route("/events", stream="iter")
    def get_events(self): ...

    export = route("/export", stream="file")


@pytest.fixture
def api(transport):
    return Api(transport=transport)


def chunks(*parts):
    return httpx.Response(200, content=iter(parts))


def test_file_mode_writes_the_body(api, recorder, tmp_path):
    recorder.respond(chunks(b"ab", b"cd"))
    target = tmp_path / "out.bin"
    response = api.download(1, file=str(target))
    assert target.read_bytes() == b"abcd"
    assert response.status_code == 200


def test_an_error_leaves_the_file_alone_and_keeps_the_error_body(api, recorder, tmp_path):
    target = tmp_path / "out.bin"
    target.write_bytes(b"old")
    recorder.respond(httpx.Response(404, content=b"not found"))
    with pytest.raises(UnexpectedResponse) as raised:
        api.download(1, file=str(target))
    assert raised.value.response.text == "not found"
    assert target.read_bytes() == b"old"


def test_a_bad_path_fails_before_the_request(api, recorder):
    with pytest.raises(ValueError, match=r"\.\."):
        api.download(1, file="../escape.bin")
    assert recorder.requests == []


def test_io_mode_writes_to_the_callers_object_and_leaves_it_open(api, recorder):
    recorder.respond(chunks(b"ab", b"cd"))
    buffer = io.BytesIO()
    api.copy_to(1, io=buffer)
    assert buffer.getvalue() == b"abcd"
    assert not buffer.closed


def test_iter_mode_returns_the_chunks(api, recorder):
    recorder.respond(chunks(b"a", b"b", b"c"))
    events = api.get_events()
    assert isinstance(events, ChunkIterator)
    assert b"".join(events) == b"abc"


def test_iter_mode_closes_when_left_early(api, recorder):
    recorder.respond(chunks(b"a", b"b"))
    with api.get_events() as events:
        assert next(events) == b"a"
    assert events.response.is_closed


def test_opening_the_stream_is_retried(api, recorder, tmp_path):
    recorder.respond(httpx.ConnectError("refused"), chunks(b"ok"))
    target = tmp_path / "out.bin"
    api.download(1, file=str(target))
    assert target.read_bytes() == b"ok"
    assert len(recorder.requests) == 2


def test_generated_routes_take_the_destination(api, recorder, tmp_path):
    recorder.respond(chunks(b"csv"))
    target = tmp_path / "export.csv"
    api.export(file=str(target))
    assert target.read_bytes() == b"csv"


def test_a_def_without_the_destination_parameter_fails_at_class_creation():
    with pytest.raises(RouteDefinitionError, match="needs a 'file' parameter"):

        class Bad(Client):
            @route("/x", stream="file")
            def get_x(self): ...


def test_unknown_stream_modes_fail():
    with pytest.raises(RouteDefinitionError, match="stream must be one of"):

        class Bad(Client):
            get_x = route("/x", stream="block")
