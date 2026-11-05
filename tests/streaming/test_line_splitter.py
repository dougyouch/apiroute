import pytest

from apiroute.streaming.line_splitter import LineSplitter


def split(chunks, encoding="utf-8"):
    splitter = LineSplitter(encoding)
    lines = []
    for chunk in chunks:
        lines.extend(splitter.feed(chunk))
    return lines + splitter.finish()


@pytest.mark.parametrize("body", [b"a\nb\nc", b"a\r\nb\r\nc", b"a\rb\rc", b"a\nb\r\nc"])
def test_splits_at_every_kind_of_line_break(body):
    assert split([body]) == ["a", "b", "c"]


def test_a_crlf_split_across_chunks_is_one_line_break():
    assert split([b"a\r", b"\nb"]) == ["a", "b"]


def test_a_lone_cr_at_a_chunk_end_still_breaks_the_line():
    assert split([b"a\r", b"b"]) == ["a", "b"]


def test_a_cr_then_an_empty_chunk_then_lf_is_one_line_break():
    assert split([b"a\r", b"", b"\nb"]) == ["a", "b"]


def test_blank_lines_are_kept():
    assert split([b"a\n\nb\r\n\r\n"]) == ["a", "", "b", ""]


def test_lines_continue_across_chunks():
    assert split([b"he", b"llo\nwor", b"ld\n"]) == ["hello", "world"]


def test_a_multibyte_character_split_across_chunks_decodes():
    encoded = "café\n".encode()
    assert split([encoded[:4], encoded[4:]]) == ["café"]


def test_the_last_line_without_a_break_is_returned_at_the_end():
    splitter = LineSplitter("utf-8")
    assert splitter.feed(b"a\nb") == ["a"]
    assert splitter.finish() == ["b"]
    assert splitter.finish() == []


def test_bytes_that_dont_decode_become_replacement_characters():
    assert split([b"a\xffb\n"]) == ["a�b"]


def test_utf8_sig_drops_a_leading_byte_order_mark():
    assert split([b"\xef\xbb", b"\xbfdata: x\n"], "utf-8-sig") == ["data: x"]


def test_other_encodings():
    assert split(["é\n".encode("latin-1")], "latin-1") == ["é"]
