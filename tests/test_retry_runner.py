import pytest

from apiroute.retries import Retries
from apiroute.retry_policy import RetryPolicy
from apiroute.retry_runner import RetryRunner


def failing(*errors, result="ok"):
    remaining = list(errors)

    def attempt():
        if remaining:
            raise remaining.pop(0)
        return result

    return attempt


def runner(retries, sleeps):
    return RetryRunner(RetryPolicy(retries, lambda error, attempt: True, "r"), sleeps.append)


def test_retries_until_success():
    sleeps = []
    result = runner(Retries(attempts=3, sleep=0.1, backoff=2), sleeps).run(
        failing(OSError(), OSError())
    )
    assert result == "ok"
    assert sleeps == pytest.approx([0.1, 0.2])


def test_raises_after_the_last_attempt():
    with pytest.raises(OSError):
        runner(Retries(attempts=2, sleep=0), []).run(failing(OSError(), OSError()))
