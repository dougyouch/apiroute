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
