import pytest

from apiroute.codegen.pagination.speakeasy_pagination import speakeasy_strategy


def strategy(extension):
    call = speakeasy_strategy(extension)
    return call.class_name, call.arguments


def test_offset_limit():
    extension = {
        "type": "offsetLimit",
        "inputs": [
            {"name": "offset", "in": "parameters", "type": "offset"},
            {"name": "limit", "in": "parameters", "type": "limit"},
        ],
        "outputs": {"results": "$.data.items"},
    }
    assert strategy(extension) == (
        "Offset",
        {"param": "offset", "limit": "limit", "items": "data.items"},
    )


def test_offset_limit_with_pages():
    extension = {
        "type": "offsetLimit",
        "inputs": [{"name": "p", "in": "parameters", "type": "page"}],
        "outputs": {"results": "$", "numPages": "$.meta.pages"},
    }
    assert strategy(extension) == (
        "PageNumber",
        {"param": "p", "total_pages": "meta.pages", "items": ""},
    )


def test_cursor_in_the_body():
    extension = {
        "type": "cursor",
        "inputs": [{"name": "since", "in": "requestBody", "type": "cursor"}],
        "outputs": {"nextCursor": "$.next", "results": "$.results"},
    }
    assert strategy(extension) == (
        "Cursor",
        {"param": "since", "token": "next", "location": "body", "items": "results"},
    )


def test_url():
    extension = {"type": "url", "outputs": {"nextUrl": "$.links.next"}}
    assert strategy(extension) == ("NextUrl", {"path": "links.next"})


@pytest.mark.parametrize(
    "extension, message",
    [
        ({"type": "pages"}, "type 'pages'"),
        ({"type": "offsetLimit", "inputs": []}, "needs an offset or page input"),
        ({"type": "url", "outputs": {"nextUrl": "$.links[0]"}}, "isn't a path of dotted keys"),
        ("cursor", "expected an object"),
    ],
)
def test_what_is_not_mapped_says_why(extension, message):
    with pytest.raises(ValueError, match=message):
        speakeasy_strategy(extension)
