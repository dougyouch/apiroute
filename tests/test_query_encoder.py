import datetime
import decimal
import enum
import uuid

import pytest

from apiroute.body_encoder import BodyEncoder
from apiroute.query_encoder import QueryEncoder


def test_flat_repeats_list_names_and_formats_booleans():
    pairs = QueryEncoder("flat").encode({"tag": ["a", "b"], "open": True, "n": 2})
    assert pairs == [("tag", "a"), ("tag", "b"), ("open", "true"), ("n", "2")]


def test_flat_rejects_dicts():
    with pytest.raises(TypeError, match="nested"):
        QueryEncoder("flat").encode({"user": {"name": "Ann"}})


def test_nested_uses_brackets_like_the_gem():
    pairs = QueryEncoder("nested").encode(
        {"user": {"name": "Ann", "tags": ["a"]}, "items": [{"id": 1}]}
    )
    assert pairs == [("user[name]", "Ann"), ("user[tags][]", "a"), ("items[][id]", "1")]


def test_rejects_unknown_styles():
    with pytest.raises(ValueError):
        QueryEncoder("rails")


class Color(enum.Enum):
    RED = "red"


class Shade(str, enum.Enum):
    BLUE = "blue"


class Level(enum.IntEnum):
    HIGH = 3


VALUES = {
    "id": uuid.UUID("12345678-1234-5678-1234-567812345678"),
    "at": datetime.datetime(2026, 1, 2, 3, 4, 5),
    "on": datetime.date(2026, 1, 2),
    "time": datetime.time(3, 4, 5),
    "amount": decimal.Decimal("1.50"),
    "color": Color.RED,
    "shade": Shade.BLUE,
    "level": Level.HIGH,
}
TEXT = {
    "id": "12345678-1234-5678-1234-567812345678",
    "at": "2026-01-02T03:04:05",
    "on": "2026-01-02",
    "time": "03:04:05",
    "amount": "1.50",
    "color": "red",
    "shade": "blue",
    "level": "3",
}


@pytest.mark.parametrize("style", ["flat", "nested"])
def test_ids_timestamps_amounts_and_enums_are_sent_as_their_wire_text(style):
    """An enum used to go out as `Color.RED` and a datetime with a space instead of a `T`."""
    assert dict(QueryEncoder(style).encode(VALUES)) == TEXT


def test_the_same_values_in_a_list_or_a_nested_dict():
    flat = QueryEncoder("flat").encode({"on": [VALUES["on"], VALUES["at"]]})
    nested = QueryEncoder("nested").encode({"range": {"from": VALUES["at"], "kind": Color.RED}})

    assert flat == [("on", "2026-01-02"), ("on", "2026-01-02T03:04:05")]
    assert nested == [("range[from]", "2026-01-02T03:04:05"), ("range[kind]", "red")]


def test_form_bodies_use_the_same_text():
    content, _ = BodyEncoder("form").encode(None, {"at": VALUES["at"], "color": Color.RED})

    assert content == "at=2026-01-02T03%3A04%3A05&color=red"


def test_multipart_fields_use_the_same_text():
    # A file makes it a real multipart body; without one the fields would be sent form-encoded.
    content, _ = BodyEncoder("multipart").encode(
        None, {**VALUES, "file": ("a.txt", b"x", "text/plain")}
    )

    for name, text in TEXT.items():
        assert f'name="{name}"\r\n\r\n{text}'.encode() in content
