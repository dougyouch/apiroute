import httpx
import pytest

from apiroute.rate_limiting.rate_limit_headers import RateLimitHeaders

NOW = 1_700_000_000.0


def pause(status=200, **headers):
    response = httpx.Response(status, headers={k.replace("_", "-"): v for k, v in headers.items()})
    return RateLimitHeaders(lambda: NOW).pause(response)


def test_the_ietf_field_with_nothing_remaining():
    assert pause(RateLimit='"default";r=0;t=30') == 30


def test_the_ietf_field_with_quota_left():
    assert pause(RateLimit='"default";r=5;t=30') is None


def test_the_ietf_field_reads_its_first_policy():
    assert pause(RateLimit='"burst";r=0;t=2, "day";r=100;t=3600') == 2


def test_the_older_ietf_fields():
    assert pause(RateLimit_Remaining="0", RateLimit_Reset="12") == 12


def test_x_ratelimit_with_seconds_to_reset():
    assert pause(X_RateLimit_Remaining="0", X_RateLimit_Reset="45") == 45


def test_x_ratelimit_with_a_unix_time():
    assert pause(X_RateLimit_Remaining="0", X_RateLimit_Reset=str(int(NOW) + 60)) == 60


def test_x_ratelimit_with_a_unix_time_in_milliseconds():
    assert pause(X_RateLimit_Remaining="0", X_RateLimit_Reset=str(int(NOW * 1000) + 5000)) == 5


def test_a_reset_in_the_past_means_no_wait():
    assert pause(X_RateLimit_Remaining="0", X_RateLimit_Reset=str(int(NOW) - 10)) == 0


@pytest.mark.parametrize("remaining", ["1", "250"])
def test_quota_left_means_no_pause(remaining):
    assert pause(X_RateLimit_Remaining=remaining, X_RateLimit_Reset="45") is None


def test_no_reset_means_no_pause():
    assert pause(X_RateLimit_Remaining="0") is None


@pytest.mark.parametrize("status", [429, 503])
def test_retry_after_on_a_429_or_503(status):
    assert pause(status, Retry_After="7") == 7


def test_retry_after_on_other_statuses_is_ignored():
    assert pause(200, Retry_After="7") is None


def test_a_429_without_retry_after_falls_back_to_the_quota_headers():
    assert pause(429, X_RateLimit_Remaining="0", X_RateLimit_Reset="3") == 3


@pytest.mark.parametrize("value", ["soon", "-1", ""])
def test_values_that_arent_numbers_are_ignored(value):
    assert pause(X_RateLimit_Remaining="0", X_RateLimit_Reset=value) is None
    assert pause(429, Retry_After=value) is None


def test_no_headers():
    assert pause() is None
