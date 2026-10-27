import asyncio

import pytest

from apiroute import Client, Retries, route
from apiroute.retry_sleeper import RETRY_SLEEPER, RetrySleeper


class Api(Client):
    base_url = "https://x.test"
    retries = Retries(attempts=2, sleep=3)

    @route("/a")
    def get_a(self): ...


def test_defaults_to_time_and_asyncio_sleep():
    import time

    assert RetrySleeper().current() == (time.sleep, asyncio.sleep)


def test_replaced_sleeps_are_used():
    sleeper = RetrySleeper()
    slept = []

    async def async_sleep(seconds):
        slept.append(-seconds)

    sleeper.replace(slept.append, async_sleep)
    sleeper.sleep(1)
    asyncio.run(sleeper.async_sleep(2))
    assert slept == [1, -2]
    sleeper.reset()
    assert sleeper.current() == RetrySleeper().current()


def test_clients_retry_through_the_process_sleeper(transport, recorder):
    import httpx

    recorder.respond(httpx.ConnectError("down"))
    slept = []
    previous = RETRY_SLEEPER.current()
    RETRY_SLEEPER.replace(slept.append, previous[1])
    try:
        Api(transport=transport).get_a()
    finally:
        RETRY_SLEEPER.replace(*previous)
    assert slept == [3]


def test_patching_a_client_sleep_still_wins(transport, recorder, monkeypatch):
    import httpx

    recorder.respond(httpx.ConnectError("down"))
    slept = []
    monkeypatch.setattr(Api, "_sleep", staticmethod(slept.append))
    Api(transport=transport).get_a()
    assert slept == [3]


@pytest.fixture(autouse=True)
def restore_sleeper():
    yield
    RETRY_SLEEPER.reset()
