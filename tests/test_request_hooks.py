from dataclasses import replace

import httpx
import pytest

from apiroute import Client, Retries, Section, UnexpectedResponse, route


class Api(Client):
    base_url = "https://x.test"
    retries = Retries(attempts=2, sleep=0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.seen = []

    def on_request(self, request):
        return replace(request, headers={**request.headers, "X-Signature": f"sig:{request.url}"})

    def on_response(self, request, response, elapsed):
        self.seen.append((request.headers["X-Signature"], response.status_code, elapsed))

    @route("/things")
    def get_things(self): ...

    @route("/events", stream="iter")
    def get_events(self): ...

    class admin(Section):
        @route("/admin")
        def get(self): ...


@pytest.fixture
def api(transport, async_transport):
    return Api(transport=transport, async_transport=async_transport)


def test_on_request_can_change_what_is_sent(api, recorder):
    api.get_things()
    assert recorder.last.headers["X-Signature"] == "sig:https://x.test/things"


def test_on_response_sees_every_attempt_with_its_timing(api, recorder):
    recorder.respond(httpx.Response(500), httpx.Response(200, json={}))
    with pytest.raises(UnexpectedResponse):
        api.get_things()
    assert [status for _, status, _ in api.seen] == [500]
    assert all(elapsed >= 0 for _, _, elapsed in api.seen)


def test_network_errors_skip_on_response_but_retries_run_it(api, recorder):
    recorder.respond(httpx.ConnectError("down"), httpx.Response(200, json={}))
    api.get_things()
    assert [status for _, status, _ in api.seen] == [200]


def test_streams_and_sections_use_the_root_clients_hooks(api, recorder):
    recorder.respond(httpx.Response(200, content=iter([b"a"])))
    with api.get_events():
        pass
    api.admin.get()
    assert recorder.last.headers["X-Signature"] == "sig:https://x.test/admin"
    assert len(api.seen) == 2


@pytest.mark.anyio
async def test_async_calls_run_the_hooks(api, recorder):
    await api.aio.get_things()
    recorder.respond(httpx.Response(200, content=b"a"))
    async with await api.aio.get_events():
        pass
    assert recorder.requests[0].headers["X-Signature"] == "sig:https://x.test/things"
    assert len(api.seen) == 2


def test_hooks_see_the_operation_name(transport, recorder):
    seen = []

    class Named(Client):
        base_url = "https://x.test"

        def on_request(self, request):
            seen.append(request.operation)

        @route("/things", operation="listThings")
        def list_things(self): ...

        @route("/other")
        def get_other(self): ...

    api = Named(transport=transport)
    api.list_things()
    api.get_other()
    assert seen == ["listThings", "get_other"]


class RateLimitedBody(Exception):
    pass


class QuotaSpent(Exception):
    pass


class BodyCodedApi(Client):
    """An API that answers 200 with an error code in the body when it rate limits."""

    base_url = "https://x.test"
    retries = Retries(attempts=3, sleep=0)

    def check_response(self, request, response):
        code = response.json().get("code") if response.content else None
        if code == 4029:
            raise RateLimitedBody(request.operation)
        if code == 4030:
            raise QuotaSpent()

    def should_retry(self, error, attempt):
        return isinstance(error, RateLimitedBody) or super().should_retry(error, attempt)

    @route("/things")
    def get_things(self): ...


@pytest.fixture
def coded(transport, async_transport):
    return BodyCodedApi(transport=transport, async_transport=async_transport)


def test_check_response_can_send_a_200_back_through_the_retry_loop(coded, recorder):
    recorder.respond(httpx.Response(200, json={"code": 4029}), httpx.Response(200, json={"ok": 1}))
    assert coded.get_things() == {"ok": 1}
    assert len(recorder.requests) == 2


def test_what_check_response_raises_propagates_when_not_retried(coded, recorder):
    recorder.respond(httpx.Response(200, json={"code": 4030}))
    with pytest.raises(QuotaSpent):
        coded.get_things()
    assert len(recorder.requests) == 1


def test_check_response_runs_before_the_status_check(coded, recorder):
    recorder.respond(httpx.Response(429, json={"code": 4029}), httpx.Response(200, json={"ok": 1}))
    assert coded.get_things() == {"ok": 1}


@pytest.mark.anyio
async def test_check_response_runs_on_async_calls_too(coded, recorder):
    recorder.respond(httpx.Response(200, json={"code": 4029}), httpx.Response(200, json={"ok": 2}))
    assert await coded.aio.get_things() == {"ok": 2}
