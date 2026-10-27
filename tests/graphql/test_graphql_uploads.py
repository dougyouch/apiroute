import io

import pytest

from apiroute.graphql import Upload
from apiroute.graphql.graphql_uploads import GraphQLUploads


def test_no_files():
    uploads = GraphQLUploads({"a": 1, "b": [1, {"c": "x"}]})
    assert not uploads
    assert uploads.variables == {"a": 1, "b": [1, {"c": "x"}]}


def test_files_at_any_depth_become_null_with_their_paths():
    a, b, c = Upload(b"a", "a.txt"), Upload(b"b", "b.txt"), Upload(b"c", "c.png")
    uploads = GraphQLUploads({"files": [a, b], "input": {"avatar": c, "name": "n"}, "n": 1})
    assert uploads.variables == {
        "files": [None, None],
        "input": {"avatar": None, "name": "n"},
        "n": 1,
    }
    assert uploads.map() == {
        "0": ["variables.files.0"],
        "1": ["variables.files.1"],
        "2": ["variables.input.avatar"],
    }
    assert uploads.files() == {
        "0": ("a.txt", b"a", "text/plain"),
        "1": ("b.txt", b"b", "text/plain"),
        "2": ("c.png", b"c", "image/png"),
    }


def test_one_file_used_twice_is_one_part():
    shared = Upload(b"s")
    uploads = GraphQLUploads({"a": shared, "b": {"c": shared}})
    assert uploads.map() == {"0": ["variables.a", "variables.b.c"]}


def test_a_bare_binary_file_is_read_in_place(tmp_path):
    path = tmp_path / "doc.json"
    path.write_bytes(b'{"x": 1}')
    with path.open("rb") as file:
        file.read(2)
        uploads = GraphQLUploads({"f": file})
        assert uploads.files() == {"0": ("doc.json", b'x": 1}', "application/json")}
        assert file.tell() == 2  # left where it was, so a second request reads it again
        assert uploads.files()["0"][1] == b'x": 1}'
    stream = io.BytesIO(b"raw")
    assert GraphQLUploads({"f": stream}).files() == {
        "0": ("upload", b"raw", "application/octet-stream")
    }


def test_text_files_are_refused(tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("x")
    with path.open() as file, pytest.raises(TypeError, match="binary mode"):
        GraphQLUploads({"f": file})
