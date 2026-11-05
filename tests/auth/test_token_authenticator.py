import asyncio
import threading
import time

import pytest

from apiroute import RequestSpec
from apiroute.auth import AccessToken, TokenAuthenticator


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Counting(TokenAuthenticator):
    def __init__(self, expires_in=None, delay=0.0, **kwargs):
        super().__init__(**kwargs)
        self.fetches = 0
        self._expires_in = expires_in
        self._delay = delay
        self._fetch_lock = threading.Lock()

    def fetch_token(self, client):
        time.sleep(self._delay)
        with self._fetch_lock:
            self.fetches += 1
            return AccessToken(f"t{self.fetches}", self._expires_in)


def request():
    return RequestSpec("GET", "https://x.test/", {"Accept": "*/*"}, [], None, None)


def test_fetches_once_and_reuses_the_token():
    auth = Counting()
    assert auth.token is None
    first = auth.credential(None)
    assert auth.credential(None) is first
    assert auth.token is first
    assert auth.fetches == 1


def test_fetches_again_leeway_seconds_before_expiry():
    clock = Clock()
    auth = Counting(expires_in=300, leeway=30, clock=clock)
    auth.credential(None)
    clock.now += 269
    assert auth.credential(None).value == "t1"
    clock.now += 1
    assert auth.credential(None).value == "t2"


def test_a_short_lived_token_is_refreshed_halfway():
    clock = Clock()
    auth = Counting(expires_in=20, leeway=30, clock=clock)
    auth.credential(None)
    clock.now += 9.9
    assert auth.fetches == 1 and auth.credential(None).value == "t1"
    clock.now += 0.1
    assert auth.credential(None).value == "t2"


def test_a_token_without_expiry_is_kept_until_invalidated():
    clock = Clock()
    auth = Counting(clock=clock)
    token = auth.credential(None)
    clock.now += 10**9
    assert auth.credential(None) is token
    auth.invalidate(token)
    assert auth.credential(None).value == "t2"


def test_invalidating_an_older_token_keeps_the_newer_one():
    auth = Counting()
    old = auth.credential(None)
    auth.invalidate(old)
    new = auth.credential(None)
    auth.invalidate(old)
    assert auth.credential(None) is new


def test_apply_sets_the_authorization_header_and_keeps_the_others():
    applied = Counting().apply(request(), AccessToken("abc"))
    assert applied.headers == {"Accept": "*/*", "Authorization": "Bearer abc"}
    assert request().headers == {"Accept": "*/*"}


def test_concurrent_threads_share_one_fetch():
    auth = Counting(delay=0.05)
    barrier = threading.Barrier(8)
    results = []

    def call():
        barrier.wait()
        results.append(auth.credential(None))

    threads = [threading.Thread(target=call) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert auth.fetches == 1
    assert len({id(token) for token in results}) == 1


def test_fetch_token_must_be_implemented():
    with pytest.raises(NotImplementedError):
        TokenAuthenticator().credential(None)


@pytest.mark.anyio
async def test_concurrent_coroutines_share_one_fetch():
    class AsyncCounting(TokenAuthenticator):
        fetches = 0

        async def afetch_token(self, client):
            await asyncio.sleep(0.01)
            self.fetches += 1
            return AccessToken(f"t{self.fetches}")

    auth = AsyncCounting()
    tokens = await asyncio.gather(*[auth.acredential(None) for _ in range(10)])
    assert auth.fetches == 1
    assert {token.value for token in tokens} == {"t1"}


@pytest.mark.anyio
async def test_afetch_token_calls_fetch_token_by_default():
    auth = Counting()
    assert (await auth.acredential(None)).value == "t1"
    assert auth.credential(None).value == "t1"


def test_each_event_loop_gets_its_own_lock():
    class AsyncCounting(TokenAuthenticator):
        fetches = 0

        async def afetch_token(self, client):
            self.fetches += 1
            return AccessToken(f"t{self.fetches}", expires_in=0)  # always stale

    auth = AsyncCounting()
    assert asyncio.run(auth.acredential(None)).value == "t1"
    assert asyncio.run(auth.acredential(None)).value == "t2"
