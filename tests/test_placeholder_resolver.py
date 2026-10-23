import pytest

from apiroute.placeholder_resolver import PlaceholderResolver


class Root:
    account_id = 7

    def region(self):
        return "eu"


def test_argument_wins_over_attribute():
    assert PlaceholderResolver({"account_id": 1}, Root())("account_id") == 1


def test_falls_back_to_attributes_and_calls_methods():
    resolve = PlaceholderResolver({}, Root())
    assert (resolve("account_id"), resolve("region")) == (7, "eu")


def test_missing_name_fails_loudly():
    with pytest.raises(AttributeError, match="org"):
        PlaceholderResolver({}, Root())("org")
