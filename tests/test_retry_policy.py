import httpx
import pytest

from apiroute.retries import Retries
from apiroute.retry_policy import RetryPolicy
from apiroute.unexpected_response import UnexpectedResponse


def unexpected(status, headers=None):
    request = httpx.Request("GET", "https://x.test/")
    return UnexpectedResponse("r", httpx.Response(status, headers=headers, request=request))


def policy(retries, should_retry=lambda error, attempt: True):
    return RetryPolicy(retries, should_retry, "r")


def test_backoff_delays_until_the_last_attempt():
    retries = Retries(attempts=3, sleep=0.1, backoff=2)
    delays = [policy(retries).delay_before_retry(OSError(), n) for n in (1, 2, 3)]
    assert delays[:2] == pytest.approx([0.1, 0.2])
    assert delays[2] is None


def test_should_retry_can_refuse():
    refuse = policy(Retries(attempts=5), should_retry=lambda error, attempt: False)
    assert refuse.delay_before_retry(OSError(), 1) is None


def test_retry_after_seconds_capped_at_max_sleep():
    capped = policy(Retries(attempts=3, sleep=0.1, max_sleep=5))
    assert capped.delay_before_retry(unexpected(503, {"Retry-After": "2"}), 1) == 2.0
    assert capped.delay_before_retry(unexpected(429, {"Retry-After": "60"}), 1) == 5


def test_retry_after_never_shortens_the_backoff():
    retries = Retries.exponential(attempts=4, initial=15, max=240)
    assert policy(retries).delay_before_retry(unexpected(429, {"Retry-After": "0"}), 1) == 15
    assert policy(retries).delay_before_retry(unexpected(429, {"Retry-After": "5"}), 2) == 30
    assert policy(retries).delay_before_retry(unexpected(429, {"Retry-After": "90"}), 2) == 90


def test_logs_retried_and_final_failures(caplog):
    logged = policy(Retries(attempts=2, sleep=0))
    logged.delay_before_retry(OSError("first"), 1)
    logged.delay_before_retry(OSError("last"), 2)
    assert "attempt 1 of 2: OSError('first')" in caplog.text
    assert "r failed on attempt 2: OSError('last')" in caplog.text


def test_an_exception_may_declare_its_log_level(caplog):
    import logging

    class Expected(Exception):
        log_level = logging.DEBUG

    policy = RetryPolicy(Retries(attempts=2, sleep=0), lambda error, attempt: True, "route")
    with caplog.at_level(logging.DEBUG, logger="apiroute.retry_policy"):
        policy.delay_before_retry(Expected(), 1)
        policy.delay_before_retry(Expected(), 2)
        policy.delay_before_retry(ValueError(), 2)
    assert [r.levelname for r in caplog.records] == ["DEBUG", "DEBUG", "WARNING"]
