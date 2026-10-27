import io

import pytest

from apiroute.graphql import Upload


def test_bytes_with_defaults():
    assert Upload(b"hi").part() == ("upload", b"hi", "application/octet-stream")
    assert Upload(b"hi", filename="a.txt").part() == ("a.txt", b"hi", "text/plain")
    assert Upload(b"hi", "a.txt", "text/csv").part() == ("a.txt", b"hi", "text/csv")


def test_a_path_is_read_when_the_part_is_made(tmp_path):
    path = tmp_path / "report.pdf"
    upload = Upload(path)
    path.write_bytes(b"%PDF")
    assert upload.part() == ("report.pdf", b"%PDF", "application/pdf")
    assert Upload(str(path)).filename == "report.pdf"


def test_a_file_object_is_read_once_and_kept(tmp_path):
    path = tmp_path / "photo.png"
    path.write_bytes(b"\x89PNG")
    with path.open("rb") as file:
        upload = Upload(file)
        assert upload.part() == ("photo.png", b"\x89PNG", "image/png")
        assert upload.part()[1] == b"\x89PNG"  # again, for a second request
    assert Upload(io.BytesIO(b"x")).filename == "upload"


def test_an_empty_path_is_refused():
    with pytest.raises(ValueError, match="needs bytes, a file path"):
        Upload("")
