import os

import pytest

from apiroute.stream_path_validator import validate_stream_path


@pytest.mark.parametrize("path", ["out.zip", "/tmp/out.zip", "reports/report..v2.csv"])
def test_accepts_ordinary_paths(path):
    assert validate_stream_path(path) == os.path.abspath(path)


@pytest.mark.parametrize(
    ("path", "message"),
    [("../etc/passwd", r"\.\."), ("a/../../b", r"\.\."), ("a\\..\\b", r"\.\."), ("a\0b", "null")],
)
def test_rejects_escapes_and_null_bytes(path, message):
    with pytest.raises(ValueError, match=message):
        validate_stream_path(path)
