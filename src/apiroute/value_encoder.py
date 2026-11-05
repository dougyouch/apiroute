import collections
import dataclasses
import datetime
import decimal
import enum
import fractions
import ipaddress
import pathlib
import uuid
import zoneinfo
from collections.abc import Callable, Mapping
from typing import Any

from apiroute.iso_duration import iso_duration

# Values with one obvious wire form, which pydantic's JSON mode writes the same way, so a plain
# value and the same value in a model are sent alike. Checked in order: an enum first, as one
# may also be a str or an int.
_TEXT = (
    uuid.UUID,
    decimal.Decimal,  # text: a JSON number is a binary float and would lose precision
    fractions.Fraction,
    ipaddress.IPv4Address,
    ipaddress.IPv6Address,
    ipaddress.IPv4Network,
    ipaddress.IPv6Network,
    pathlib.PurePath,
    zoneinfo.ZoneInfo,
)
CONVERSIONS: tuple[tuple[Any, Callable[[Any], Any]], ...] = (
    (enum.Enum, lambda value: value.value),
    ((datetime.datetime, datetime.date, datetime.time), lambda value: value.isoformat()),
    (datetime.timedelta, iso_duration),
    (_TEXT, str),
    ((set, frozenset, collections.deque), list),
    (Mapping, dict),
)


class ValueEncoder:
    """Turns a value JSON can't hold into one it can: the default behind Client.encode_value,
    used for JSON bodies and GraphQL variables, and, through text_value, for query, form and
    multipart values.

    Covers what database drivers (psycopg, asyncpg, SQLAlchemy) and the standard library hand
    back: UUIDs, dates, times and datetimes (ISO 8601), timedeltas (ISO 8601 durations, such
    as a Postgres interval), Decimals, Fractions, IP addresses and networks (inet, cidr), paths,
    time zones, enums (their value), sets, other mappings, dataclasses and pydantic models (their
    fields, by wire name), and numpy scalars and arrays.

    The result may itself need converting (an enum whose value is a UUID, a dataclass holding a
    datetime); json.dumps and text_value call again for it. Anything else is a TypeError, so a
    value with no obvious wire form (bytes: base64 or text?) is never guessed at.
    """

    def encode(self, value: Any) -> Any:
        for types, convert in CONVERSIONS:
            if isinstance(value, types):
                return convert(value)
        if _is_dataclass_instance(value):
            return {field.name: getattr(value, field.name) for field in dataclasses.fields(value)}
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json", by_alias=True, exclude_unset=True)
        if _is_numpy(value):
            return value.tolist()
        raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _is_dataclass_instance(value: Any) -> bool:
    return dataclasses.is_dataclass(value) and not isinstance(value, type)


def _is_numpy(value: Any) -> bool:
    """numpy is optional, so it's recognised by module rather than imported."""
    return type(value).__module__ == "numpy" and hasattr(value, "tolist")


VALUE_ENCODER = ValueEncoder()
