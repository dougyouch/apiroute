from dataclasses import dataclass
from typing import Annotated, Any, Optional

import pytest

pytest.importorskip("pydantic")
from pydantic import BaseModel

from apiroute.model_types import is_model_type, is_pydantic_model


@dataclass
class Point:
    x: int


class User(BaseModel):
    id: int


def test_models_anywhere_in_the_type_count():
    for tp in (
        Point,
        User,
        list[Point],
        dict[str, User],
        Optional[Point],  # noqa: UP045 -- the typing spelling is what is under test
        Point | None,
        Annotated[list[User], "meta"],
    ):
        assert is_model_type(tp), tp


def test_plain_types_do_not():
    for tp in (dict, list, str, Any, dict[str, Any], list[int], None):
        assert not is_model_type(tp), tp


def test_pydantic_detection():
    assert is_pydantic_model(User)
    assert not is_pydantic_model(Point)


def test_generic_aliases_are_not_classes():
    # On Python 3.10 isinstance(list[User], type) is True; this must not reach issubclass
    assert not is_pydantic_model(list[User])
    assert not is_pydantic_model(dict[str, User])
