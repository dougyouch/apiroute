import pytest

from apiroute.base_url_validator import validate_base_url


@pytest.mark.parametrize("url", ["https://api.example.com", "http://localhost:8080/v1"])
def test_accepts_web_urls(url):
    validate_base_url(url)


@pytest.mark.parametrize(
    ("url", "message"),
    [("file:///etc/passwd", "scheme"), ("gopher://x", "scheme"), ("https://", "no host")],
)
def test_rejects_other_urls(url, message):
    with pytest.raises(ValueError, match=message):
        validate_base_url(url)
