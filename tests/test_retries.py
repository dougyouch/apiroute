import random

import pytest

from apiroute.retries import Retries


def test_defaults_match_the_gem():
    assert Retries() == Retries(attempts=1, sleep=0.05, backoff=1, max_sleep=None, jitter=False)


def test_backoff_and_cap():
    retries = Retries(attempts=5, sleep=0.1, backoff=2, max_sleep=0.3)
    assert [retries.delay(n) for n in (1, 2, 3, 4)] == pytest.approx([0.1, 0.2, 0.3, 0.3])


def test_exponential_shorthand():
    assert Retries.exponential(attempts=5, initial=0.1, max=10) == Retries(
        5, 0.1, backoff=2, max_sleep=10
    )


def test_full_jitter_stays_within_the_delay():
    retries = Retries(attempts=2, sleep=1, jitter=True)
    rng = random.Random(1)
    assert all(0 <= retries.delay(1, rng) <= 1 for _ in range(50))


def test_partial_jitter_shortens_by_at_most_the_fraction():
    retries = Retries(attempts=2, sleep=1, jitter=0.5)
    rng = random.Random(1)
    assert all(0.5 <= retries.delay(1, rng) <= 1 for _ in range(50))


@pytest.mark.parametrize("kwargs", [{"attempts": 0}, {"jitter": 1.5}])
def test_rejects_bad_values(kwargs):
    with pytest.raises(ValueError):
        Retries(**kwargs)
