import datetime
import decimal
import enum
import json
import uuid

import pytest

from apiroute.json_default import json_default

ID = uuid.UUID("12345678-1234-5678-1234-567812345678")


class Color(enum.Enum):
    RED = "red"


class Level(enum.IntEnum):
    HIGH = 3


class ById(enum.Enum):
    ONE = ID


def dumps(value):
    return json.dumps(value, default=json_default)


def test_a_uuid_is_its_canonical_text():
    assert dumps({"id": ID}) == '{"id": "12345678-1234-5678-1234-567812345678"}'


def test_dates_and_times_are_iso_8601():
    assert dumps(datetime.datetime(2026, 1, 2, 3, 4, 5)) == '"2026-01-02T03:04:05"'
    assert dumps(datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)) == (
        '"2026-01-02T03:04:05+00:00"'
    )
    assert dumps(datetime.date(2026, 1, 2)) == '"2026-01-02"'
    assert dumps(datetime.time(3, 4, 5)) == '"03:04:05"'


def test_a_decimal_is_text_so_no_precision_is_lost():
    assert dumps(decimal.Decimal("10.10")) == '"10.10"'


def test_an_enum_is_its_value():
    assert dumps(Color.RED) == '"red"'
    assert dumps(Level.HIGH) == "3"
    assert dumps(ById.ONE) == '"12345678-1234-5678-1234-567812345678"'  # converted again


def test_values_nest_inside_lists_and_dicts():
    assert json.loads(dumps({"a": [ID, {"at": datetime.date(2026, 1, 2)}]})) == {
        "a": [str(ID), {"at": "2026-01-02"}]
    }


@pytest.mark.parametrize("value", [object(), {1, 2}, b"x", 1 + 2j])
def test_anything_else_is_still_an_error(value):
    with pytest.raises(TypeError, match="not JSON serializable"):
        dumps(value)
