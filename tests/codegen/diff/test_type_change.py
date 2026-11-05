import pytest

from apiroute.codegen.diff.type_change import type_change


@pytest.mark.parametrize(
    ("old", "new", "kind"),
    [
        ("str", "str", None),
        ("str", "int", "breaking"),
        ("str", "str | None", "breaking"),
        ("Literal['a']", "Literal['a', 'b']", "addition"),
        ("Literal['a', 'b'] | None", "Literal['a', 'b', 'c'] | None", "addition"),
        ("Literal['a', 'b']", "Literal['a']", "breaking"),
        ("Literal['a']", "Literal['b']", "breaking"),
        ("Literal['a']", "str", "breaking"),
        ("Literal[x]", "Literal[x, 'b']", "breaking"),  # not constants: can't tell
        ("not valid(", "Literal['a']", "breaking"),
    ],
)
def test_type_change(old, new, kind):
    assert type_change(old, new) == kind
