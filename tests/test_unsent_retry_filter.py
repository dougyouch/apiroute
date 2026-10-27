import httpx
import pytest

from apiroute.unsent_retry_filter import UnsentRetryFilter


def always(error, attempt):
    return True


@pytest.mark.parametrize(
    "error",
    [httpx.ReadTimeout("t"), httpx.WriteTimeout("t"), httpx.ReadError("r"), httpx.WriteError("w"),
     httpx.RemoteProtocolError("p")],
)  # fmt: skip
def test_never_retries_an_error_after_sending(error):
    assert UnsentRetryFilter(always)(error, 1) is False


@pytest.mark.parametrize(
    "error", [httpx.ConnectError("c"), httpx.ConnectTimeout("t"), httpx.PoolTimeout("p")]
)
def test_leaves_errors_before_sending_to_should_retry(error):
    assert UnsentRetryFilter(always)(error, 1) is True
    assert UnsentRetryFilter(lambda error, attempt: False)(error, 1) is False


def test_passes_the_attempt_through():
    seen = []
    UnsentRetryFilter(lambda error, attempt: seen.append(attempt))(ValueError(), 3)
    assert seen == [3]
