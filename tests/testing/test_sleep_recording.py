import asyncio
import time

import pytest

from apiroute.retry_sleeper import RETRY_SLEEPER
from apiroute.testing import recorded_sleeps


def test_waits_are_recorded_instead_of_slept():
    with recorded_sleeps() as sleeps:
        RETRY_SLEEPER.sleep(5)
        asyncio.run(RETRY_SLEEPER.async_sleep(7))
    assert sleeps == [5, 7]


def test_waits_go_to_a_given_list():
    given = []
    with recorded_sleeps(given) as sleeps:
        RETRY_SLEEPER.sleep(1)
    assert sleeps is given
    assert given == [1]


def test_the_previous_sleeps_come_back_on_exit():
    with pytest.raises(ZeroDivisionError), recorded_sleeps():
        raise ZeroDivisionError
    assert RETRY_SLEEPER.current() == (time.sleep, asyncio.sleep)
