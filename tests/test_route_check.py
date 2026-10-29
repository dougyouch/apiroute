import httpx
import pytest

from apiroute import Client, Retries, RouteDefinitionError, UnexpectedResponse, route


class StatusError(Exception):
    pass


def ok(response):
    return response.json().get("status") != "error"


def raise_on_error(response):
    body = response.json()
    if body.get("status") == "error":
        raise StatusError(body["message"])


class Api(Client):
    base_url = "https://x.test"
    retries = Retries(attempts=3, sleep=0)

    def should_retry(self, error, attempt):
        return isinstance(error, StatusError) or super().should_retry(error, attempt)

    @route("/orders", check=ok)
    def get_orders(self): ...

    @route("/payments", check=raise_on_error)
    def get_payments(self): ...

    get_refunds = route("/refunds", check=ok)


@pytest.fixture
def api(transport, async_transport):
    return Api(transport=transport, async_transport=async_transport)


def test_a_false_check_rejects_a_200(api, recorder):
    recorder.respond(httpx.Response(200, json={"status": "error"}))
    with pytest.raises(UnexpectedResponse, match="get_orders: rejected by check") as raised:
        api.get_orders()
    assert raised.value.response.json() == {"status": "error"}
    assert len(recorder.requests) == 1


def test_a_passing_check_returns_the_result(api, recorder):
    recorder.respond(httpx.Response(200, json={"status": "ok", "orders": []}))
    assert api.get_orders() == {"status": "ok", "orders": []}


def test_routes_without_a_def_take_a_check(api, recorder):
    recorder.respond(httpx.Response(200, json={"status": "error"}))
    with pytest.raises(UnexpectedResponse, match="get_refunds: rejected by check"):
        api.get_refunds()


def test_what_a_check_raises_goes_through_should_retry(api, recorder):
    recorder.respond(
        httpx.Response(200, json={"status": "error", "message": "busy"}),
        httpx.Response(200, json={"status": "ok"}),
    )
    assert api.get_payments() == {"status": "ok"}
    assert len(recorder.requests) == 2


def test_what_a_check_raises_propagates_once_retries_run_out(api, recorder):
    recorder.respond(*[httpx.Response(200, json={"status": "error", "message": "x"})] * 3)
    with pytest.raises(StatusError, match="x"):
        api.get_payments()
    assert len(recorder.requests) == 3


@pytest.mark.anyio
async def test_async_calls_run_the_check(api, recorder):
    recorder.respond(httpx.Response(200, json={"status": "error"}))
    with pytest.raises(UnexpectedResponse, match="rejected by check"):
        await api.aio.get_orders()


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"check": "status"}, "check= takes a callable"),
        ({"check": ok, "stream": "iter"}, "check= reads the body"),
    ],
)
def test_bad_checks_fail_at_class_creation(kwargs, message):
    with pytest.raises(RouteDefinitionError, match=message):

        class Bad(Client):
            @route("/x", **kwargs)
            def get_x(self): ...
