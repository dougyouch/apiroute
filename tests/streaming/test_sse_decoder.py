from apiroute.streaming.server_sent_event import ServerSentEvent
from apiroute.streaming.sse_decoder import SseDecoder


def decode(*lines, decoder=None):
    decoder = decoder or SseDecoder()
    events = []
    for line in lines:
        events.extend(decoder.feed(line))
    return events + decoder.end()


def test_a_blank_line_dispatches_the_event():
    assert decode("data: hello", "") == [ServerSentEvent("hello")]


def test_data_lines_are_joined_with_newlines():
    assert decode("data: a", "data: b", "") == [ServerSentEvent("a\nb")]


def test_the_event_field_sets_the_type_for_one_event():
    events = decode("event: update", "data: 1", "", "data: 2", "")
    assert [(e.event, e.data) for e in events] == [("update", "1"), ("message", "2")]


def test_an_empty_event_field_means_message():
    assert decode("event:", "data: x", "")[0].event == "message"


def test_only_one_leading_space_is_removed():
    assert decode("data:  two", "data:none", "") == [ServerSentEvent(" two\nnone")]


def test_a_field_without_a_colon_has_an_empty_value():
    assert decode("data", "data", "") == [ServerSentEvent("\n")]


def test_a_value_may_hold_colons():
    assert decode("data: a: b", "") == [ServerSentEvent("a: b")]


def test_comments_and_unknown_fields_are_ignored():
    assert decode(": keep-alive", "foo: bar", "data: x", "") == [ServerSentEvent("x")]


def test_an_event_without_data_is_not_dispatched():
    assert decode("event: ping", "", ": comment", "") == []


def test_an_event_type_without_data_doesnt_leak_into_the_next_event():
    assert decode("event: ping", "", "data: x", "")[0].event == "message"


def test_the_id_carries_over_to_later_events():
    events = decode("id: 7", "data: a", "", "data: b", "")
    assert [e.id for e in events] == ["7", "7"]


def test_an_empty_id_resets_it():
    events = decode("id: 7", "data: a", "", "id", "data: b", "")
    assert [e.id for e in events] == ["7", None]


def test_an_id_with_a_null_is_ignored():
    events = decode("id: 7", "data: a", "", "id: 8\0", "data: b", "")
    assert [e.id for e in events] == ["7", "7"]


def test_an_id_counts_once_its_event_is_dispatched():
    decoder = SseDecoder()
    decode("id: 1", "data: a", "", "id: 2", "data: b", decoder=decoder)
    assert decoder.last_event_id == "1"


def test_a_blank_line_without_data_still_updates_the_last_event_id():
    decoder = SseDecoder()
    decode("id: 5", "", decoder=decoder)
    assert decoder.last_event_id == "5"


def test_retry_takes_only_ascii_digits():
    decoder = SseDecoder()
    decode("retry: 1500", decoder=decoder)
    assert decoder.retry == 1500
    decode("retry: 2s", "retry: -1", "retry: ٣", "retry:", decoder=decoder)
    assert decoder.retry == 1500


def test_an_unfinished_event_at_the_end_is_dropped():
    assert decode("data: complete", "", "data: partial") == [ServerSentEvent("complete")]


def test_reset_drops_the_partial_event_and_its_id():
    decoder = SseDecoder()
    decode("id: 1", "data: a", "", "id: 2", "event: x", "data: partial", decoder=decoder)
    decoder.reset()
    assert decode("data: b", "", decoder=decoder) == [ServerSentEvent("b", "message", "1")]
