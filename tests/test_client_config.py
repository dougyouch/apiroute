import pytest

from apiroute import Client, Retries, Section
from apiroute.client_config import ClientConfig


def test_headers_merge_down_subclasses_and_none_removes():
    class Base(Client):
        base_url = "https://x.test"
        headers = {"A": "1", "B": "2"}

    class Child(Base):
        headers = {"B": None, "C": "3"}

    assert Child._config.headers == {"A": "1", "C": "3"}
    assert Child._config.base_url == "https://x.test"


def test_other_settings_are_replaced():
    class Base(Client):
        retries = Retries(attempts=3)

    class Child(Base):
        retries = Retries(attempts=2)

    assert Child._config.retries.attempts == 2


@pytest.mark.parametrize(
    ("attribute", "value", "message"),
    [
        ("base_url", "ftp://x.test", "scheme"),
        ("body_format", "xml", "body_format"),
        ("query_format", "rails", "query_format"),
        ("retries", 3, "Retries"),
        ("inherit", ("base_url",), "inherit"),
    ],
)
def test_invalid_settings_fail_at_class_creation(attribute, value, message):
    with pytest.raises(ValueError, match=message):
        type("Bad", (Client,), {attribute: value})


def test_section_takes_parent_base_url_and_only_what_it_inherits():
    root = ClientConfig(base_url="https://x.test", headers={"A": "1"}, query_params={"k": "v"})
    section = ClientConfig(headers={"B": "2"}, inherit=frozenset({"headers"}))
    config = section.for_section(root, root)
    assert config.base_url == "https://x.test"
    assert config.headers == {"A": "1", "B": "2"}
    assert config.query_params == {}


def test_section_class_config_is_its_own():
    class Api(Client):
        headers = {"A": "1"}

        class things(Section):
            pass

    assert Api.things._config.headers == {}
