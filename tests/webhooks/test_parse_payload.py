import json
from dataclasses import dataclass

import pytest

from apiroute.webhooks import parse_payload
from tests.conftest import needs_pydantic


@dataclass
class Event:
    type: str


def test_parses_bytes_and_text():
    assert parse_payload(b'{"a": 1}') == {"a": 1}
    assert parse_payload("[1, 2]") == [1, 2]


def test_parsed_data_passes_through():
    assert parse_payload({"a": 1}) == {"a": 1}


def test_converts_to_a_dataclass_or_a_list_of_them():
    assert parse_payload(b'{"type": "x"}', Event) == Event("x")
    assert parse_payload(b'[{"type": "x"}]', list[Event]) == [Event("x")]


def test_a_body_that_isnt_json_raises():
    with pytest.raises(json.JSONDecodeError):
        parse_payload(b"nope")


@needs_pydantic
def test_converts_to_pydantic_models():
    from pydantic import BaseModel, ValidationError

    class Paid(BaseModel):
        amount: int

    assert parse_payload(b'{"amount": 5}', Paid) == Paid(amount=5)
    with pytest.raises(ValidationError):
        parse_payload(b'{"amount": "lots"}', Paid)
