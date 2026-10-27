import re

# Block strings, strings, names, numbers, the spread and single punctuators. Whitespace,
# commas and # comments separate tokens and are dropped, as GraphQL ignores them.
_TOKEN = re.compile(
    r'"""(?:\\"""|[^"]|"(?!""))*"""'
    r'|"(?:\\.|[^"\\\n])*"'
    r"|[_A-Za-z][_0-9A-Za-z]*"
    r"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?"
    r"|\.\.\."
    r"|[!$&():=@\[\]{|}]"
)
_IGNORED = re.compile(r"(?:[\s,﻿]|#[^\n\r]*)+")


def tokenize(document: str) -> list[str]:
    """The document's tokens, enough to read its operations; raises ValueError on a
    character GraphQL doesn't allow, such as an unterminated string."""
    tokens = []
    position = _skip_ignored(document, 0)
    while position < len(document):
        match = _TOKEN.match(document, position)
        if match is None:
            raise ValueError(f"unexpected character {document[position]!r} at {position}")
        tokens.append(match.group())
        position = _skip_ignored(document, match.end())
    return tokens


def _skip_ignored(document: str, position: int) -> int:
    match = _IGNORED.match(document, position)
    return match.end() if match else position
