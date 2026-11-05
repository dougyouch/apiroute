import json
from dataclasses import dataclass

import httpx
import pytest

from apiroute.item_converter import ItemConverter
from apiroute.streaming.ndjson_decoder import NdjsonDecoder


def plain():
    return ItemConverter(None, lambda: None)


def test_each_line_is_a_json_value():
    decoder = NdjsonDecoder(plain())
    assert decoder.feed('{"a": 1}') == [{"a": 1}]
    assert decoder.feed("[1, 2]") == [[1, 2]]
    assert decoder.end() == []


def test_blank_lines_are_skipped():
    assert NdjsonDecoder(plain()).feed("   ") == []


def test_values_are_converted():
    @dataclass
    class Row:
        a: int

    assert NdjsonDecoder(ItemConverter(Row, lambda: None)).feed('{"a": 1}') == [Row(1)]


def test_a_line_that_isnt_json_raises():
    with pytest.raises(json.JSONDecodeError):
        NdjsonDecoder(plain()).feed("{oops")


def test_it_reads_utf8_whatever_the_header_says():
    response = httpx.Response(200, headers={"Content-Type": "application/x-ndjson"})
    assert NdjsonDecoder(plain()).encoding(response) == "utf-8-sig"
