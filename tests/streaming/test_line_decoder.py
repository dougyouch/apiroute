import httpx

from apiroute.streaming.line_decoder import LineDecoder


def test_lines_pass_through():
    decoder = LineDecoder()
    assert decoder.feed("x") == ["x"]
    assert decoder.feed("") == [""]
    assert decoder.end() == []


def test_the_declared_charset_else_utf8():
    latin = httpx.Response(200, headers={"Content-Type": "text/plain; charset=latin-1"})
    assert LineDecoder().encoding(latin) == "latin-1"
    assert LineDecoder().encoding(httpx.Response(200)) == "utf-8"
