import pytest

pytest.importorskip("pydantic")
from pydantic import BaseModel, ValidationError

from apiroute.pydantic_converter import PydanticConverter


class User(BaseModel):
    id: int
    login: str


def test_validates_and_coerces():
    assert PydanticConverter(list[User]).convert([{"id": "1", "login": "a"}]) == [
        User(id=1, login="a")
    ]


def test_invalid_data_raises_pydantics_error():
    with pytest.raises(ValidationError):
        PydanticConverter(User).convert({"id": "x"})
