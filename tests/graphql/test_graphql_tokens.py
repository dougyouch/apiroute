import pytest

from apiroute.graphql.graphql_tokens import tokenize


def test_drops_whitespace_commas_and_comments():
    assert tokenize("query A($x: Int, $y: [ID!]!) # note ($z)\n{ a }") == [
        "query", "A", "(", "$", "x", ":", "Int", "$", "y", ":", "[", "ID", "!", "]", "!", ")",
        "{", "a", "}",
    ]  # fmt: skip


def test_keeps_strings_whole():
    assert tokenize('{ a(s: "($x) # no") b(t: """multi "quoted" ($y)""") }') == [
        "{", "a", "(", "s", ":", '"($x) # no"', ")", "b", "(", "t", ":",
        '"""multi "quoted" ($y)"""', ")", "}",
    ]  # fmt: skip


def test_numbers_and_spreads():
    assert tokenize("{ a(n: -1.5e3) ...F }") == [
        "{",
        "a",
        "(",
        "n",
        ":",
        "-1.5e3",
        ")",
        "...",
        "F",
        "}",
    ]


def test_rejects_an_unterminated_string():
    with pytest.raises(ValueError, match="unexpected character"):
        tokenize('{ a(s: "open) }')
