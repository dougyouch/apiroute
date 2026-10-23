import pytest

from apiroute.async_retry_runner import AsyncRetryRunner
from apiroute.retries import Retries
from apiroute.retry_policy import RetryPolicy


def failing(*errors, result="ok"):
    remaining = list(errors)

    async def attempt():
        if remaining:
            raise remaining.pop(0)
        return result

    return attempt


def runner(retries, sleeps):
    async def sleep(delay):
        sleeps.append(delay)

    return AsyncRetryRunner(RetryPolicy(retries, lambda error, attempt: True, "r"), sleep)


@pytest.mark.anyio
async def test_retries_until_success():
    sleeps = []
    result = await runner(Retries(attempts=3, sleep=0.1, backoff=2), sleeps).run(
        failing(OSError(), OSError())
    )
    assert result == "ok"
    assert sleeps == pytest.approx([0.1, 0.2])


@pytest.mark.anyio
async def test_raises_after_the_last_attempt():
    with pytest.raises(OSError):
        await runner(Retries(attempts=2, sleep=0), []).run(failing(OSError(), OSError()))
