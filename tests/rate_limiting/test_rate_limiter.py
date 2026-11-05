import threading

import httpx
import pytest

from apiroute.rate_limiting import RateLimiter


class Clock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now


def limiter(clock, **kwargs):
    return RateLimiter(clock=clock, wall_clock=lambda: 1_700_000_000.0, **kwargs)


def test_up_to_the_burst_goes_at_once_then_requests_are_spaced_out():
    clock = Clock()
    rl = limiter(clock, requests=2, per=1.0)
    assert [rl.reserve() for _ in range(5)] == [0, 0, 0.5, 1.0, 1.5]


def test_the_bucket_refills_over_time():
    clock = Clock()
    rl = limiter(clock, requests=2, per=1.0)
    rl.reserve(), rl.reserve()
    clock.now += 0.5
    assert rl.reserve() == 0
    assert rl.reserve() == 0.5


def test_the_bucket_never_holds_more_than_the_burst():
    clock = Clock()
    rl = limiter(clock, requests=10, per=60.0, burst=2)
    clock.now += 3600
    assert [rl.reserve() for _ in range(3)] == [0, 0, 6.0]


def test_a_burst_of_one_spaces_every_request():
    clock = Clock()
    rl = limiter(clock, requests=1, per=2.0)
    assert [rl.reserve() for _ in range(3)] == [0, 2.0, 4.0]


def test_fractional_rates():
    clock = Clock()
    rl = limiter(clock, requests=0.5, per=1.0)
    assert [rl.reserve() for _ in range(2)] == [0, 2.0]


def test_headers_pause_every_request_until_the_reset():
    clock = Clock()
    rl = limiter(clock, headers=True)
    assert rl.reserve() == 0
    rl.observe(
        httpx.Response(200, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "30"})
    )
    assert rl.reserve() == 30
    clock.now += 10
    assert rl.reserve() == 20
    clock.now += 20
    assert rl.reserve() == 0


def test_a_later_shorter_pause_doesnt_shorten_an_earlier_one():
    clock = Clock()
    rl = limiter(clock, headers=True)
    rl.observe(httpx.Response(429, headers={"Retry-After": "30"}))
    rl.observe(httpx.Response(429, headers={"Retry-After": "5"}))
    assert rl.reserve() == 30


def test_headers_are_ignored_unless_asked_for():
    clock = Clock()
    rl = limiter(clock, requests=10)
    rl.observe(httpx.Response(429, headers={"Retry-After": "30"}))
    assert rl.reserve() == 0


def test_both_take_the_longer_wait():
    clock = Clock()
    rl = limiter(clock, requests=1, per=1.0, headers=True)
    rl.reserve()
    rl.observe(httpx.Response(429, headers={"Retry-After": "0.25"}))
    assert rl.reserve() == 1.0


def test_threads_each_get_their_own_slot():
    clock = Clock()
    rl = limiter(clock, requests=1, per=1.0)
    waits = []
    lock = threading.Lock()

    def take():
        wait = rl.reserve()
        with lock:
            waits.append(wait)

    threads = [threading.Thread(target=take) for _ in range(10)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(waits) == [float(n) for n in range(10)]


@pytest.mark.parametrize(
    ("kwargs", "problem"),
    [
        ({}, "needs requests=, headers=True or both"),
        ({"requests": 0}, "requests must be more than 0"),
        ({"requests": 1, "per": 0}, "per must be more than 0"),
        ({"requests": 1, "burst": 0}, "burst must be at least 1"),
    ],
)
def test_invalid_settings(kwargs, problem):
    with pytest.raises(ValueError, match=problem):
        RateLimiter(**kwargs)
