import asyncio
import json

import httpx
import pytest

from apiroute import Client, Retries, graphql_route
from apiroute.graphql import Upload
from apiroute.testing import MockTransport, graphql_response
from tests.graphql.multipart import parse_multipart

UPLOAD = (
    "mutation Upload($file: Upload!, $tags: [String!]) { upload(file: $file, tags: $tags) { id } }"
)


class Files(Client):
    base_url = "https://files.test"
    retries = Retries(attempts=2, sleep=0)
    upload = graphql_route(UPLOAD, data="upload.id", idempotent=True)
    persisted_upload = graphql_route(UPLOAD, data="upload.id", persisted=True)


@pytest.fixture
def mock():
    return MockTransport()


@pytest.fixture
def files(mock):
    return Files(transport=mock, async_transport=mock.aio)


def parts(call):
    return parse_multipart(call.content, call.headers["Content-Type"])


def test_a_call_with_a_file(files, mock):
    mock.respond(graphql_response(data={"upload": {"id": "f1"}}))
    assert files.upload(file=Upload(b"hello", "a.txt"), tags=["x"]) == "f1"
    operations, file_map, part = parts(mock.last)
    assert json.loads(operations[3])["variables"] == {"file": None, "tags": ["x"]}
    assert json.loads(file_map[3]) == {"0": ["variables.file"]}
    assert part == ("0", "a.txt", "text/plain", b"hello")
    assert mock.last.operation == "Upload"


def test_a_call_without_a_file_is_still_json(mock):
    class Api(Client):
        base_url = "https://files.test"
        viewer = graphql_route("query V { viewer { id } }")

    mock.respond(graphql_response(data={"viewer": None}))
    Api(transport=mock).viewer()
    assert mock.last.headers["Content-Type"] == "application/json"


def test_async(files, mock):
    mock.respond(graphql_response(data={"upload": {"id": "f2"}}))
    assert asyncio.run(files.aio.upload(file=Upload(b"x", "x.bin"))) == "f2"
    assert parts(mock.last)[2][3] == b"x"


def test_a_retry_resends_the_same_file(files, mock, tmp_path):
    path = tmp_path / "data.csv"
    path.write_bytes(b"a,b\n1,2\n")
    mock.respond(httpx.ConnectError("refused"), graphql_response(data={"upload": {"id": "f3"}}))
    with path.open("rb") as file:
        assert files.upload(file=file) == "f3"
    first, second = (parts(call) for call in mock.calls)
    assert first == second
    assert first[2] == ("0", "data.csv", "text/csv", b"a,b\n1,2\n")


def test_a_persisted_upload_registers_with_the_same_file(files, mock, tmp_path):
    path = tmp_path / "photo.png"
    path.write_bytes(b"\x89PNG")
    miss = graphql_response(errors=[{"message": "PersistedQueryNotFound"}])
    mock.respond(miss, graphql_response(data={"upload": {"id": "f4"}}))
    with path.open("rb") as file:
        assert files.persisted_upload(file=file) == "f4"
    hashed, registered = (parts(call) for call in mock.calls)
    assert "query" not in json.loads(hashed[0][3])
    assert "query" in json.loads(registered[0][3])
    assert hashed[2] == registered[2] == ("0", "photo.png", "image/png", b"\x89PNG")
