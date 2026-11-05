import httpx
import pytest

from apiroute import RequestSpec
from apiroute.caching import ConditionalCache


def get(url="https://x.test/a", params=(), method="GET", **headers):
    names = {k.replace("_", "-"): v for k, v in headers.items()}
    return RequestSpec(method, url, names, list(params), None, None)


def ok(content=b'{"v": 1}', **headers):
    names = {k.replace("_", "-"): v for k, v in headers.items()}
    return httpx.Response(
        200, headers=names, content=content, request=httpx.Request("GET", "https://x.test/a")
    )


def not_modified(**headers):
    names = {k.replace("_", "-"): v for k, v in headers.items()}
    return httpx.Response(304, headers=names, request=httpx.Request("GET", "https://x.test/a"))


def test_nothing_kept_means_the_request_is_unchanged():
    assert ConditionalCache().prepare(get()) == get()


def test_a_response_with_an_etag_makes_the_next_request_conditional():
    cache = ConditionalCache()
    cache.resolve(get(), ok(ETag='"v1"'))
    assert cache.prepare(get()).headers == {"If-None-Match": '"v1"'}


def test_last_modified_is_sent_as_if_modified_since():
    cache = ConditionalCache()
    stamp = "Wed, 21 Oct 2026 07:28:00 GMT"
    cache.resolve(get(), ok(Last_Modified=stamp))
    assert cache.prepare(get()).headers == {"If-Modified-Since": stamp}


def test_both_validators_are_sent():
    cache = ConditionalCache()
    cache.resolve(get(), ok(ETag='"v1"', Last_Modified="x"))
    assert cache.prepare(get()).headers == {"If-None-Match": '"v1"', "If-Modified-Since": "x"}


def test_a_304_returns_the_kept_body_as_a_200():
    cache = ConditionalCache()
    cache.resolve(get(), ok(ETag='"v1"', Content_Type="application/json", X_Old="1"))
    response = cache.resolve(
        get(), not_modified(ETag='"v1"', X_RateLimit_Remaining="59", Date="d2")
    )
    assert response.status_code == 200
    assert response.json() == {"v": 1}
    assert response.extensions["apiroute_cache"] == "revalidated"
    assert response.headers["X-RateLimit-Remaining"] == "59"
    assert response.headers["X-Old"] == "1"
    assert response.headers["Content-Type"] == "application/json"


def test_a_304_without_a_kept_response_is_returned_as_is():
    response = not_modified()
    assert ConditionalCache().resolve(get(), response) is response


def test_a_new_200_replaces_the_kept_response():
    cache = ConditionalCache()
    cache.resolve(get(), ok(ETag='"v1"'))
    cache.resolve(get(), ok(b'{"v": 2}', ETag='"v2"'))
    assert cache.prepare(get()).headers["If-None-Match"] == '"v2"'
    assert cache.resolve(get(), not_modified()).json() == {"v": 2}


@pytest.mark.parametrize("headers", [{}, {"Cache-Control": "private, no-store"}, {"Vary": "*"}])
def test_responses_that_cant_be_kept(headers):
    cache = ConditionalCache()
    response = httpx.Response(
        200, headers={"ETag": '"v1"', **headers} if headers else {}, content=b"x"
    )
    cache.resolve(get(), response)
    assert len(cache) == 0


def test_only_gets_are_cached():
    cache = ConditionalCache()
    cache.resolve(get(method="POST"), ok(ETag='"v1"'))
    assert len(cache) == 0
    assert cache.prepare(get(method="HEAD")) == get(method="HEAD")


def test_other_statuses_arent_kept():
    cache = ConditionalCache()
    cache.resolve(get(), httpx.Response(201, headers={"ETag": '"v1"'}))
    assert len(cache) == 0


def test_a_request_the_caller_made_conditional_is_left_alone():
    cache = ConditionalCache()
    cache.resolve(get(), ok(ETag='"v1"'))
    mine = get(If_None_Match='"mine"')
    assert cache.prepare(mine) == mine
    response = not_modified()
    assert cache.resolve(mine, response) is response


def test_each_url_and_query_has_its_own_entry():
    cache = ConditionalCache()
    cache.resolve(get(params=[("page", "1")]), ok(ETag='"p1"'))
    assert cache.prepare(get(params=[("page", "2")])).headers == {}
    assert cache.prepare(get(params=[("page", "1")])).headers == {"If-None-Match": '"p1"'}
    assert cache.prepare(get("https://x.test/a?page=1")).headers == {"If-None-Match": '"p1"'}


def test_callers_with_different_credentials_never_share():
    cache = ConditionalCache()
    cache.resolve(get(Authorization="Bearer ann"), ok(ETag='"ann"'))
    assert cache.prepare(get(Authorization="Bearer bob")).headers == {"Authorization": "Bearer bob"}
    assert cache.prepare(get()).headers == {}
    assert cache.prepare(get(Authorization="Bearer ann")).headers["If-None-Match"] == '"ann"'


def test_cookies_separate_callers_too():
    cache = ConditionalCache()
    cache.resolve(get(Cookie="s=1"), ok(ETag='"one"'))
    assert "If-None-Match" not in cache.prepare(get(Cookie="s=2")).headers


def test_vary_headers_must_match():
    cache = ConditionalCache()
    cache.resolve(get(Accept_Language="en"), ok(ETag='"en"', Vary="Accept-Language, Accept"))
    assert "If-None-Match" not in cache.prepare(get(Accept_Language="fr")).headers
    assert cache.prepare(get(Accept_Language="en")).headers["If-None-Match"] == '"en"'
    response = not_modified()
    assert cache.resolve(get(Accept_Language="fr"), response) is response


def test_the_least_recently_used_entry_is_dropped():
    cache = ConditionalCache(max_entries=2)
    for name in ("a", "b"):
        cache.resolve(get(f"https://x.test/{name}"), ok(ETag=f'"{name}"'))
    cache.prepare(get("https://x.test/a"))  # a is now the most recently used
    cache.resolve(get("https://x.test/c"), ok(ETag='"c"'))
    assert len(cache) == 2
    assert "If-None-Match" not in cache.prepare(get("https://x.test/b")).headers
    assert "If-None-Match" in cache.prepare(get("https://x.test/a")).headers


def test_clear():
    cache = ConditionalCache()
    cache.resolve(get(), ok(ETag='"v1"'))
    cache.clear()
    assert len(cache) == 0


def test_max_entries_must_be_positive():
    with pytest.raises(ValueError, match="at least 1"):
        ConditionalCache(max_entries=0)
