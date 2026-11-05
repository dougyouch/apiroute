import httpx
import pytest

from apiroute import Client, Retries, Section, UnexpectedResponse, route
from apiroute.pagination import NextUrl
from apiroute.rate_limiting import RateLimiter
from apiroute.testing.sleep_recording import recorded_sleeps


class Frozen:
    """A clock that stands still, so each wait is exactly what the bucket computes."""

    def __call__(self):
        return 100.0


def api_class(limiter):
    class Api(Client):
        base_url = "https://x.test"
        rate_limiter = limiter
        get_x = route("/x")
        events = route("/events", stream="sse")
        listing = route("/list", paginate=NextUrl())

        class admin(Section):
            get_y = route("/y")

        class reports(Section):
            rate_limiter = RateLimiter(requests=100, clock=Frozen())
            get_z = route("/z")

    return Api


@pytest.fixture
def api(transport):
    return api_class(RateLimiter(requests=2, per=1.0, clock=Frozen()))(transport=transport)


def test_calls_past_the_burst_wait(api):
    with recorded_sleeps() as sleeps:
        for _ in range(4):
            api.get_x()
    assert sleeps == [0.5, 1.0]


def test_sections_share_the_clients_budget_unless_they_set_their_own(api):
    with recorded_sleeps() as sleeps:
        api.get_x()
        api.admin.get_y()
        api.reports.get_z()
        api.admin.get_y()
    assert sleeps == [0.5]


def test_instances_of_a_class_share_a_class_level_limiter(transport):
    Api = api_class(RateLimiter(requests=1, per=1.0, clock=Frozen()))
    with recorded_sleeps() as sleeps:
        Api(transport=transport).get_x()
        Api(transport=transport).get_x()
    assert sleeps == [1.0]


def test_every_page_counts(transport, recorder):
    recorder.respond(
        httpx.Response(200, json=[1], headers={"Link": '<https://x.test/list?p=2>; rel="next"'}),
        httpx.Response(200, json=[2], headers={"Link": '<https://x.test/list?p=3>; rel="next"'}),
        httpx.Response(200, json=[3]),
    )
    Api = api_class(RateLimiter(requests=1, per=1.0, clock=Frozen()))
    with recorded_sleeps() as sleeps:
        assert list(Api(transport=transport).listing()) == [1, 2, 3]
    assert sleeps == [1.0, 2.0]


def test_retries_count(transport, recorder):
    class Retrying(api_class(RateLimiter(requests=1, per=1.0, clock=Frozen()))):
        retries = Retries(attempts=2, sleep=0)

    recorder.respond(httpx.ConnectError("x"), httpx.Response(200, json={}))
    with recorded_sleeps() as sleeps:
        Retrying(transport=transport).get_x()
    assert sleeps == [0, 1.0]  # the retry's own backoff, then the rate limiter's wait


def test_streams_count(api, recorder):
    recorder.respond(*[httpx.Response(200, content=b"data: a\n\n") for _ in range(3)])
    with recorded_sleeps() as sleeps:
        for _ in range(3):
            list(api.events())
    assert sleeps == [0.5]


def test_header_pauses_apply_to_the_next_request(transport, recorder):
    Api = api_class(RateLimiter(headers=True, clock=Frozen()))
    api = Api(transport=transport)
    recorder.respond(
        httpx.Response(
            200, json={}, headers={"X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "30"}
        ),
        httpx.Response(200, json={}),
    )
    with recorded_sleeps() as sleeps:
        api.get_x()
        api.get_x()
    assert sleeps == [30]


def test_a_429_pauses_every_caller(transport, recorder):
    Api = api_class(RateLimiter(headers=True, clock=Frozen()))
    recorder.respond(
        httpx.Response(429, headers={"Retry-After": "12"}), httpx.Response(200, json={})
    )
    with recorded_sleeps() as sleeps:
        with pytest.raises(UnexpectedResponse):
            Api(transport=transport).get_x()
        Api(transport=transport).admin.get_y()
    assert sleeps == [12]


def test_a_setting_that_isnt_a_rate_limiter_fails():
    with pytest.raises(ValueError, match="rate_limiter must be"):

        class Bad(Client):
            rate_limiter = 10


@pytest.mark.anyio
async def test_async_calls_wait_without_blocking(async_transport):
    api = api_class(RateLimiter(requests=1, per=1.0, clock=Frozen()))(
        async_transport=async_transport
    )
    with recorded_sleeps() as sleeps:
        await api.aio.get_x()
        await api.aio.get_x()
        list_events = await api.aio.events()
        [event async for event in list_events]
    assert sleeps == [1.0, 2.0]


@pytest.mark.anyio
async def test_async_header_pauses(async_transport, recorder):
    api = api_class(RateLimiter(headers=True, clock=Frozen()))(async_transport=async_transport)
    recorder.respond(httpx.Response(200, json={}, headers={"RateLimit": '"d";r=0;t=4'}))
    with recorded_sleeps() as sleeps:
        await api.aio.get_x()
        await api.aio.get_x()
    assert sleeps == [4]
