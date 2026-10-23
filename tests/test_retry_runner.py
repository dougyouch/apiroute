import httpx
import pytest

from apiroute.retries import Retries
from apiroute.retry_runner import RetryRunner
from apiroute.unexpected_response import UnexpectedResponse


def failing(*errors, result="ok"):
    remaining = list(errors)

    def attempt():
        if remaining:
            raise remaining.pop(0)
        return result

    return attempt


def unexpected(status, headers=None):
    request = httpx.Request("GET", "https://x.test/")
    return UnexpectedResponse("r", httpx.Response(status, headers=headers, request=request))


def run(attempt, retries, should_retry=lambda error, n: True):
    sleeps = []
    result = RetryRunner(retries, should_retry, sleeps.append).run(attempt, "r")
    return result, sleeps


def test_retries_until_success_with_backoff():
    retries = Retries(attempts=3, sleep=0.1, backoff=2)
    result, sleeps = run(failing(OSError(), OSError()), retries)
    assert result == "ok"
    assert sleeps == pytest.approx([0.1, 0.2])


def test_raises_after_the_last_attempt():
    with pytest.raises(OSError):
        run(failing(OSError(), OSError()), Retries(attempts=2, sleep=0))


def test_does_not_retry_when_should_retry_says_no():
    with pytest.raises(OSError):
        run(failing(OSError()), Retries(attempts=5), should_retry=lambda error, n: False)


def test_uses_retry_after_seconds_capped_at_max_sleep():
    retries = Retries(attempts=3, sleep=0.1, max_sleep=5)
    _, sleeps = run(
        failing(unexpected(503, {"Retry-After": "2"}), unexpected(429, {"Retry-After": "60"})),
        retries,
    )
    assert sleeps == [2.0, 5]


def test_logs_each_failure(caplog):
    run(failing(OSError("boom")), Retries(attempts=2, sleep=0))
    assert "attempt 1 of 2" in caplog.text
    assert "boom" in caplog.text
