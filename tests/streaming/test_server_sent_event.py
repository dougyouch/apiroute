import json

import pytest

from apiroute.streaming import ServerSentEvent


def test_json_parses_the_data():
    assert ServerSentEvent('{"delta": "hi"}').json() == {"delta": "hi"}


def test_json_raises_for_data_that_isnt_json():
    with pytest.raises(json.JSONDecodeError):
        ServerSentEvent("[DONE]").json()


def test_defaults():
    event = ServerSentEvent("x")
    assert (event.event, event.id) == ("message", None)
