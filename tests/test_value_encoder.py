import collections
import dataclasses
import datetime
import decimal
import enum
import fractions
import ipaddress
import json
import pathlib
import types
import uuid
import zoneinfo

import pydantic
import pytest

from apiroute.value_encoder import VALUE_ENCODER

ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


class Color(enum.Enum):
    RED = "red"


class Level(enum.IntEnum):
    HIGH = 3


class ById(enum.Enum):
    ONE = ID


@dataclasses.dataclass
class Window:
    start: datetime.date
    length: datetime.timedelta


class Account(pydantic.BaseModel):
    account_id: uuid.UUID = pydantic.Field(alias="accountId")
    note: str | None = None


def dumps(value):
    return json.dumps(value, default=VALUE_ENCODER.encode)


def test_a_uuid_is_its_canonical_text():
    assert dumps({"id": ID}) == '{"id": "12345678-1234-5678-1234-567812345678"}'


def test_dates_and_times_are_iso_8601():
    assert dumps(datetime.datetime(2026, 1, 2, 3, 4, 5)) == '"2026-01-02T03:04:05"'
    assert dumps(datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)) == (
        '"2026-01-02T03:04:05+00:00"'
    )
    assert dumps(datetime.date(2026, 1, 2)) == '"2026-01-02"'
    assert dumps(datetime.time(3, 4, 5)) == '"03:04:05"'


def test_a_timedelta_is_an_iso_8601_duration():
    assert dumps(datetime.timedelta(days=1, hours=2)) == '"P1DT2H"'


def test_a_decimal_is_text_so_no_precision_is_lost():
    assert dumps(decimal.Decimal("10.10")) == '"10.10"'
    assert dumps(fractions.Fraction(1, 3)) == '"1/3"'


@pytest.mark.parametrize(
    ("value", "text"),
    [
        (ipaddress.ip_address("10.0.0.1"), "10.0.0.1"),
        (ipaddress.ip_address("::1"), "::1"),
        (ipaddress.ip_network("10.0.0.0/8"), "10.0.0.0/8"),
        (ipaddress.ip_interface("10.0.0.1/24"), "10.0.0.1/24"),
        (pathlib.PurePosixPath("/a/b"), "/a/b"),
        (zoneinfo.ZoneInfo("UTC"), "UTC"),
    ],
)
def test_addresses_networks_paths_and_zones_are_text(value, text):
    assert dumps(value) == json.dumps(text)


def test_an_enum_is_its_value():
    assert dumps(Color.RED) == '"red"'
    assert dumps(Level.HIGH) == "3"
    assert dumps(ById.ONE) == '"12345678-1234-5678-1234-567812345678"'  # converted again


def test_sets_and_other_collections_are_lists_and_mappings_are_objects():
    assert dumps(frozenset([ID])) == f'["{ID}"]'
    assert dumps(collections.deque([1, 2])) == "[1, 2]"
    assert dumps(types.MappingProxyType({"a": ID})) == f'{{"a": "{ID}"}}'


def test_a_dataclass_is_its_fields_converted_in_turn():
    window = Window(datetime.date(2026, 1, 2), datetime.timedelta(hours=1))
    assert json.loads(dumps(window)) == {"start": "2026-01-02", "length": "PT1H"}


def test_a_pydantic_model_is_its_set_fields_by_wire_name():
    assert json.loads(dumps(Account(accountId=ID))) == {"accountId": str(ID)}


def test_values_nest_inside_lists_and_dicts():
    assert json.loads(dumps({"a": [ID, {"at": datetime.date(2026, 1, 2)}]})) == {
        "a": [str(ID), {"at": "2026-01-02"}]
    }


@pytest.mark.parametrize("value", [object(), b"x", 1 + 2j, Window])
def test_anything_without_an_obvious_wire_form_is_still_an_error(value):
    with pytest.raises(TypeError, match="not JSON serializable"):
        dumps(value)
