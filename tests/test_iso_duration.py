import datetime

import pytest

from apiroute.iso_duration import iso_duration


@pytest.mark.parametrize(
    ("delta", "text"),
    [
        (datetime.timedelta(0), "PT0S"),
        (datetime.timedelta(days=1), "P1D"),
        (datetime.timedelta(days=1, hours=2, minutes=3, seconds=4.5), "P1DT2H3M4.5S"),
        (datetime.timedelta(minutes=5), "PT5M"),
        (datetime.timedelta(microseconds=1), "PT0.000001S"),
        (datetime.timedelta(seconds=-90), "-PT1M30S"),
        (datetime.timedelta(days=-1), "-P1D"),
    ],
)
def test_writes_iso_8601_durations(delta, text):
    assert iso_duration(delta) == text
