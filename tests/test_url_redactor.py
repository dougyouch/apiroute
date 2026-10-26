import pytest

from apiroute.url_redactor import UrlRedactor

redactor = UrlRedactor()


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://x.test/a?api_key=abc&page=2", "https://x.test/a?api_key=***&page=2"),
        ("https://x.test/a?apikey=abc", "https://x.test/a?apikey=***"),
        ("https://x.test/a?accessToken=abc&sort=asc", "https://x.test/a?accessToken=***&sort=asc"),
        ("https://x.test/a?client-secret=s&sig=t", "https://x.test/a?client-secret=***&sig=***"),
        ("https://x.test/a?token=1&token=2", "https://x.test/a?token=***&token=***"),
        ("https://x.test/a?X-Api-Key=k", "https://x.test/a?X-Api-Key=***"),
        ("https://x.test/a?keyword=moon&monkey=1", "https://x.test/a?keyword=moon&monkey=1"),
        ("https://x.test/a?flag&token=", "https://x.test/a?flag&token=***"),
        ("https://x.test/a", "https://x.test/a"),
        ("https://ann:hunter2@x.test/a", "https://ann:***@x.test/a"),
        ("https://ann@x.test/a", "https://ann@x.test/a"),
    ],
)
def test_secret_values_are_masked_and_everything_else_kept(url, expected):
    assert redactor.redact(url) == expected


def test_encoded_names_are_recognised():
    assert redactor.redact("https://x.test/?api%5Fkey=abc") == "https://x.test/?api%5Fkey=***"


def test_the_secret_words_can_be_replaced():
    assert UrlRedactor(frozenset({"code"})).redact("https://x.test/?code=1&token=2") == (
        "https://x.test/?code=***&token=2"
    )
