from dataclasses import dataclass

import httpx
import pytest

from apiroute import Client, Retries, RouteDefinitionError, UnexpectedResponse, route
from apiroute.polling import OperationFailed, Poll, PollTimeout
from apiroute.testing.sleep_recording import recorded_sleeps


@dataclass
class Export:
    id: str
    rows: int


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class Api(Client):
    base_url = "https://x.test/v1"
    retries = Retries(attempts=2, sleep=0)

    @route("POST", "/exports", poll=Poll(interval=2))
    def export(self, body: dict) -> Export: ...

    @route("POST", "/raw-exports", poll=Poll())
    def raw_export(self, body: dict): ...

    @route("POST", "/jobs", poll=Poll(result="output"))
    def job(self): ...

    @route("POST", "/vms", poll=Poll(result_url="resourceLocation"))
    def create_vm(self) -> Export: ...

    @route("POST", "/text", poll=Poll(), returns="text")
    def text_job(self): ...


@pytest.fixture
def api(transport):
    return Api(transport=transport)


def accepted(location="/v1/ops/1", **headers):
    names = {name.replace("_", "-"): value for name, value in headers.items()}
    return httpx.Response(202, headers={"Location": location, **names})


def test_polls_until_the_operation_succeeds_and_converts_its_body(api, recorder):
    recorder.respond(
        accepted(),
        httpx.Response(200, json={"status": "running"}),
        httpx.Response(200, json={"status": "succeeded", "id": "e1", "rows": 9}),
    )
    with recorded_sleeps() as sleeps:
        assert api.export({"table": "users"}) == Export("e1", 9)
    assert sleeps == [2, 2]
    first, *polls = recorder.requests
    assert (first.method, first.url.path) == ("POST", "/v1/exports")
    assert [(p.method, str(p.url)) for p in polls] == [("GET", "https://x.test/v1/ops/1")] * 2
    assert all(p.content == b"" and "content-type" not in p.headers for p in polls)


def test_a_response_that_isnt_a_202_is_the_result(api, recorder):
    recorder.respond(httpx.Response(201, json={"id": "e1", "rows": 1}))
    assert api.export({}) == Export("e1", 1)
    assert len(recorder.requests) == 1


def test_the_result_path(api, recorder):
    recorder.respond(accepted(), httpx.Response(200, json={"status": "done", "output": [1, 2]}))
    with recorded_sleeps():
        assert api.job() == [1, 2]


def test_a_result_url_is_fetched(api, recorder):
    recorder.respond(
        accepted(Retry_After="7"),
        httpx.Response(200, json={"status": "Succeeded", "resourceLocation": "/v1/vms/1"}),
        httpx.Response(200, json={"id": "vm1", "rows": 0}),
    )
    with recorded_sleeps() as sleeps:
        assert api.create_vm() == Export("vm1", 0)
    assert sleeps == [7]
    assert recorder.last.url.path == "/v1/vms/1"


def test_a_303_is_followed_to_the_result(api, recorder):
    recorder.respond(
        accepted(),
        httpx.Response(303, headers={"Location": "https://x.test/v1/exports/e1"}),
        httpx.Response(200, json={"id": "e1", "rows": 3}),
    )
    with recorded_sleeps():
        assert api.export({}) == Export("e1", 3)


def test_relative_status_urls_resolve_against_the_request(api, recorder):
    recorder.respond(accepted("ops/9?verbose=1"), httpx.Response(200, json={"id": "x", "rows": 1}))
    with recorded_sleeps():
        api.export({})
    assert str(recorder.last.url) == "https://x.test/v1/ops/9?verbose=1"


def test_a_failed_operation_raises(api, recorder):
    recorder.respond(accepted(), httpx.Response(200, json={"status": "failed", "reason": "quota"}))
    with recorded_sleeps(), pytest.raises(OperationFailed) as raised:
        api.export({})
    assert raised.value.body["reason"] == "quota"
    assert raised.value.response.status_code == 200


def test_an_error_status_while_polling_raises(api, recorder):
    recorder.respond(accepted(), httpx.Response(404))
    with recorded_sleeps(), pytest.raises(UnexpectedResponse, match="404"):
        api.export({})


def test_an_error_status_on_the_first_response_raises(api, recorder):
    recorder.respond(httpx.Response(400))
    with pytest.raises(UnexpectedResponse, match="400"):
        api.export({})


def test_polls_are_retried_like_reads_though_the_post_isnt(api, recorder):
    recorder.respond(
        accepted(),
        httpx.ReadError("dropped"),
        httpx.Response(200, json={"id": "e", "rows": 1}),
    )
    with recorded_sleeps():
        assert api.export({}) == Export("e", 1)
    recorder.respond(httpx.ReadError("dropped"))
    with pytest.raises(httpx.ReadError):
        api.export({})


def test_a_status_url_on_another_host_is_refused(api, recorder):
    recorder.respond(accepted("https://evil.test/ops/1"))
    with pytest.raises(ValueError, match="evil.test"):
        api.export({})
    assert len(recorder.requests) == 1


def test_running_past_the_timeout_raises(transport, recorder):
    clock = Clock()

    class Slow(Client):
        base_url = "https://x.test"
        start = route("POST", "/ops", poll=Poll(interval=10, timeout=25, clock=clock))

    def sleep(seconds):
        clock.now += seconds

    recorder.respond(
        accepted("/ops/1?token=secret"), *[httpx.Response(200, json={"status": "running"})] * 5
    )
    from apiroute.retry_sleeper import RETRY_SLEEPER

    previous = RETRY_SLEEPER.current()
    RETRY_SLEEPER.replace(sleep, previous[1])
    try:
        with pytest.raises(PollTimeout) as raised:
            Slow(transport=transport).start()
    finally:
        RETRY_SLEEPER.replace(*previous)
    assert raised.value.timeout == 25
    assert "secret" not in raised.value.url
    assert len(recorder.requests) == 3  # the POST, then polls at 10s and 20s; 30s is too late


def test_the_client_headers_and_credentials_go_with_each_poll(transport, recorder):
    class Authed(Api):
        headers = {"Authorization": "Bearer t", "X-Api-Version": "3"}

    recorder.respond(accepted(), httpx.Response(200, json={"id": "e", "rows": 1}))
    with recorded_sleeps():
        Authed(transport=transport).export({})
    assert recorder.last.headers["Authorization"] == "Bearer t"
    assert recorder.last.headers["X-Api-Version"] == "3"


def test_returns_applies_to_the_result(api, recorder):
    recorder.respond(accepted(), httpx.Response(200, text="all done"))
    with recorded_sleeps():
        assert api.text_job() == "all done"


def test_with_options_returns_response(api, recorder):
    recorder.respond(accepted(), httpx.Response(200, json={"status": "done"}))
    with recorded_sleeps():
        response = api.with_options(returns="response").raw_export({})
    assert isinstance(response, httpx.Response)


def test_poll_cant_take_stream_or_paginate():
    from apiroute.pagination import NextUrl

    for options in ({"stream": "sse"}, {"paginate": NextUrl()}):
        with pytest.raises(RouteDefinitionError, match="poll= waits for one result"):

            class Bad(Client):
                go = route("/x", poll=Poll(), **options)


def test_poll_takes_a_poll():
    with pytest.raises(RouteDefinitionError, match="poll= takes a Poll"):

        class Bad(Client):
            go = route("/x", poll=5)


@pytest.mark.anyio
async def test_async_polling(async_transport, recorder):
    recorder.respond(
        accepted(Retry_After="3"),
        httpx.ReadError("dropped"),
        httpx.Response(200, json={"status": "running"}),
        httpx.Response(303, headers={"Location": "/v1/exports/e1"}),
        httpx.Response(200, json={"id": "e1", "rows": 2}),
    )
    with recorded_sleeps() as sleeps:
        assert await Api(async_transport=async_transport).aio.export({}) == Export("e1", 2)
    assert sleeps == [3, 0, 2]


@pytest.mark.anyio
async def test_async_without_polling(async_transport, recorder):
    recorder.respond(httpx.Response(200, json={"id": "e1", "rows": 2}))
    assert await Api(async_transport=async_transport).aio.export({}) == Export("e1", 2)
