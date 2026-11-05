import datetime
import uuid

import httpx
import pytest

from apiroute import Client, route
from apiroute.testing import MockTransport


class Range:
    """Stands in for a driver type apiroute doesn't know, such as a psycopg Range."""

    def __init__(self, lower, upper):
        self.lower = lower
        self.upper = upper

    def __str__(self):
        return f"[{self.lower},{self.upper})"


class Bookings(Client):
    base_url = "https://x.test"

    @route("POST", "/bookings")
    def create(self, body): ...

    @route("GET", "/bookings", query={"during": "{during}"})
    def search(self, during): ...

    @route("POST", "/bookings/form", body_format="form")
    def create_form(self, body): ...


class RangeBookings(Bookings):
    def encode_value(self, value):
        if isinstance(value, Range):
            return {"lower": value.lower, "upper": value.upper}
        return super().encode_value(value)


class DayRangeBookings(Bookings):
    def encode_value(self, value):
        if isinstance(value, Range):
            return f"{value.lower}..{value.upper}"
        return super().encode_value(value)


@pytest.fixture
def mock():
    mock = MockTransport()
    mock.respond(*[httpx.Response(200, json={})] * 2)
    return mock


def test_an_unknown_type_is_still_an_error_by_default(mock):
    with pytest.raises(TypeError, match="Range is not JSON serializable"):
        Bookings(transport=mock).create({"during": Range(1, 2)})


def test_an_override_converts_its_own_types_and_keeps_the_defaults(mock):
    day = datetime.date(2026, 1, 2)
    RangeBookings(transport=mock).create({"during": Range(day, day), "id": uuid.UUID(int=1)})

    assert mock.last.json() == {
        "during": {"lower": "2026-01-02", "upper": "2026-01-02"},  # converted again
        "id": "00000000-0000-0000-0000-000000000001",
    }


def test_query_and_form_values_use_the_override_too(mock):
    client = DayRangeBookings(transport=mock)

    client.search(during=Range(1, 5))
    assert mock.last.params["during"] == "1..5"

    client.create_form({"during": Range(1, 5)})
    assert mock.last.content == b"during=1..5"


def test_query_values_without_a_conversion_are_their_text(mock):
    Bookings(transport=mock).search(during=Range(1, 5))

    assert mock.last.params["during"] == "[1,5)"
