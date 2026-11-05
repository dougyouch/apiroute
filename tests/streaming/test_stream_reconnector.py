import httpx
import pytest

from apiroute.retries import Retries
from apiroute.retry_policy import RetryPolicy
from apiroute.streaming.async_stream_reconnector import AsyncStreamReconnector
from apiroute.streaming.sse_decoder import SseDecoder
from apiroute.streaming.stream_reconnector import StreamReconnector


def policy(attempts=3, should_retry=lambda error, attempt: True):
    return RetryPolicy(Retries(attempts=attempts, sleep=0.5), should_retry, "events")


def decoder(*lines):
    sse = SseDecoder()
    for line in lines:
        sse.feed(line)
    return sse


def test_reopens_with_the_last_event_id_after_the_backoff():
    sleeps, reopened = [], []
    reconnector = StreamReconnector(policy(), sleeps.append, lambda h: reopened.append(h) or "s")
    assert reconnector.reopen(httpx.ReadError("x"), 1, decoder("id: 9", "data: a", "")) == "s"
    assert reopened == [{"Last-Event-ID": "9"}]
    assert sleeps == [0.5]


def test_without_an_event_id_no_header_is_sent():
    reopened = []
    reconnector = StreamReconnector(policy(), lambda s: None, lambda h: reopened.append(h))
    reconnector.reopen(httpx.ReadError("x"), 1, decoder())
    assert reopened == [{}]


def test_the_servers_retry_time_lengthens_the_wait():
    sleeps = []
    reconnector = StreamReconnector(policy(), sleeps.append, lambda h: None)
    reconnector.reopen(httpx.ReadError("x"), 1, decoder("retry: 3000"))
    assert sleeps == [3.0]


def test_the_backoff_wins_over_a_shorter_retry_time():
    sleeps = []
    reconnector = StreamReconnector(policy(), sleeps.append, lambda h: None)
    reconnector.reopen(httpx.ReadError("x"), 1, decoder("retry: 10"))
    assert sleeps == [0.5]


def test_raises_the_error_when_the_policy_says_stop():
    reconnector = StreamReconnector(policy(attempts=2), lambda s: None, lambda h: None)
    error = httpx.ReadError("x")
    with pytest.raises(httpx.ReadError) as raised:
        reconnector.reopen(error, 2, decoder())
    assert raised.value is error


def test_raises_the_error_when_should_retry_refuses():
    refusing = policy(should_retry=lambda error, attempt: False)
    with pytest.raises(httpx.ReadError):
        StreamReconnector(refusing, lambda s: None, lambda h: None).reopen(
            httpx.ReadError("x"), 1, decoder()
        )


@pytest.mark.anyio
async def test_the_async_reconnector_awaits_the_sleep_and_the_reopen():
    sleeps, reopened = [], []

    async def sleep(seconds):
        sleeps.append(seconds)

    async def reopen(headers):
        reopened.append(headers)
        return "s"

    reconnector = AsyncStreamReconnector(policy(), sleep, reopen)
    assert await reconnector.reopen(httpx.ReadError("x"), 1, decoder("id: 1", "")) == "s"
    assert (sleeps, reopened) == ([0.5], [{"Last-Event-ID": "1"}])


@pytest.mark.anyio
async def test_the_async_reconnector_raises_when_the_policy_says_stop():
    async def never(*args):
        raise AssertionError("not called")

    reconnector = AsyncStreamReconnector(policy(attempts=1), never, never)
    with pytest.raises(httpx.ReadError):
        await reconnector.reopen(httpx.ReadError("x"), 1, decoder())
