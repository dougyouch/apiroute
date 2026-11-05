import datetime
import decimal
import json
import uuid

from apiroute.body_encoder import BodyEncoder


def test_json():
    assert BodyEncoder("json").encode(None, {"a": 1}) == (b'{"a": 1}', "application/json")


def test_form():
    content, content_type = BodyEncoder("form").encode(None, {"a": "x y", "b": {"c": 1}})
    assert content == "a=x+y&b%5Bc%5D=1"
    assert content_type == "application/x-www-form-urlencoded"


def test_strings_and_bytes_are_sent_as_is():
    assert BodyEncoder("json").encode(None, "<xml/>") == ("<xml/>", None)
    assert BodyEncoder("json").encode(None, b"\x00") == (b"\x00", None)


def test_callable_gets_the_client_and_data():
    encoder = BodyEncoder(lambda client, data: f"{client}:{data['a']}")
    assert encoder.encode("me", {"a": 1}) == ("me:1", None)


def test_multipart_fields_and_files():
    content, content_type = BodyEncoder("multipart").encode(
        None, {"title": "x", "draft": True, "file": ("a.txt", b"hello", "text/plain"), "skip": None}
    )
    assert content_type.startswith("multipart/form-data; boundary=")
    assert b'name="title"\r\n\r\nx' in content
    assert b'name="draft"\r\n\r\ntrue' in content
    assert b'filename="a.txt"' in content and b"hello" in content
    assert b'name="skip"' not in content


def test_json_bodies_carry_ids_timestamps_and_amounts():
    content, _ = BodyEncoder("json").encode(
        None,
        {
            "id": uuid.UUID("12345678-1234-5678-1234-567812345678"),
            "at": datetime.datetime(2026, 1, 2, 3, 4, 5),
            "on": datetime.date(2026, 1, 2),
            "amount": decimal.Decimal("10.50"),
        },
    )

    assert json.loads(content) == {
        "id": "12345678-1234-5678-1234-567812345678",
        "at": "2026-01-02T03:04:05",
        "on": "2026-01-02",
        "amount": "10.50",
    }
