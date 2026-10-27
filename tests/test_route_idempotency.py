import asyncio

import httpx
import pytest

from apiroute import Client, Retries, Section, UnexpectedResponse, graphql_route, route
from apiroute.testing import MockTransport, graphql_response

OK = httpx.Response(200, json={"ok": True})


class Api(Client):
    base_url = "https://api.test"
    retries = Retries(attempts=3, sleep=0)

    @route("GET", "/items")
    def list_items(self): ...

    @route("HEAD", "/items")
    def head_items(self): ...

    @route("OPTIONS", "/items")
    def item_options(self): ...

    @route("POST", "/items")
    def create_item(self): ...

    @route("PUT", "/items/1")
    def replace_item(self): ...

    @route("PATCH", "/items/1")
    def update_item(self): ...

    @route("DELETE", "/items/1")
    def delete_item(self): ...

    @route("POST", "/search", idempotent=True)
    def search(self): ...

    @route("GET", "/report", idempotent=False)
    def run_report(self): ...

    @route("POST", "/charges", idempotency_key="Idempotency-Key")
    def charge(self): ...

    def should_retry(self, error, attempt):
        retried = isinstance(error, UnexpectedResponse) and error.status_code == 503
        return retried or super().should_retry(error, attempt)


@pytest.fixture
def mock():
    return MockTransport()


@pytest.fixture
def api(mock):
    return Api(transport=mock, async_transport=mock.aio)


def attempts_after_read_timeout(method_name):
    mock = MockTransport()
    mock.respond(httpx.ReadTimeout("slow"), OK)
    try:
        getattr(Api(transport=mock), method_name)()
    except httpx.ReadTimeout:
        pass
    return len(mock.calls)


@pytest.mark.parametrize(
    "method_name, attempts",
    [
        ("list_items", 2),
        ("head_items", 2),
        ("item_options", 2),
        ("create_item", 1),
        ("replace_item", 1),
        ("update_item", 1),
        ("delete_item", 1),
        ("search", 2),  # POST declared idempotent
        ("run_report", 1),  # GET declared not idempotent
        ("charge", 2),  # POST with an idempotency key
    ],
)
def test_which_routes_retry_after_a_read_timeout(method_name, attempts):
    assert attempts_after_read_timeout(method_name) == attempts


def test_errors_before_sending_are_retried_for_every_method(api, mock):
    mock.respond(httpx.ConnectError("refused"), OK)
    assert api.create_item() == {"ok": True}
    assert len(mock.calls) == 2


def test_retried_statuses_still_go_through_should_retry(api, mock):
    mock.respond(httpx.Response(503), OK)
    assert api.create_item() == {"ok": True}
    assert len(mock.calls) == 2


def test_async_follows_the_same_rules():
    post_mock, get_mock = MockTransport(), MockTransport()
    post_mock.respond(httpx.ReadTimeout("slow"), OK)
    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(Api(async_transport=post_mock.aio).aio.create_item())
    assert len(post_mock.calls) == 1
    get_mock.respond(httpx.ReadTimeout("slow"), OK)
    assert asyncio.run(Api(async_transport=get_mock.aio).aio.list_items()) == {"ok": True}
    assert len(get_mock.calls) == 2


def test_one_key_per_call_the_same_on_every_retry(api, mock):
    mock.respond(httpx.ReadTimeout("slow"), OK, OK)
    api.charge()
    first, retry = (call.headers["Idempotency-Key"] for call in mock.calls)
    assert first == retry
    assert len(first) == 36  # a UUID4
    api.charge()
    assert mock.last.headers["Idempotency-Key"] != first


def test_hooks_see_the_key(mock):
    seen = []

    class Hooked(Api):
        def on_request(self, request):
            seen.append(request.headers.get("Idempotency-Key"))

    mock.respond(httpx.ReadTimeout("slow"), OK)
    Hooked(transport=mock).charge()
    assert len(seen) == 2 and seen[0] == seen[1] is not None


def test_the_callers_own_key_is_kept(api, mock):
    mock.respond(httpx.ReadTimeout("slow"), OK)
    api.with_options(headers={"idempotency-key": "mine"}).charge()
    assert [call.headers["Idempotency-Key"] for call in mock.calls] == ["mine", "mine"]


def test_a_removed_key_means_no_retry(api, mock):
    mock.respond(httpx.ReadTimeout("slow"), OK)
    with pytest.raises(httpx.ReadTimeout):
        api.with_options(headers={"Idempotency-Key": None}).charge()
    assert "Idempotency-Key" not in mock.last.headers
    assert len(mock.calls) == 1


class Payments(Client):
    base_url = "https://pay.test"
    retries = Retries(attempts=3, sleep=0)
    idempotency_key = "Idempotency-Key"

    @route("GET", "/charges")
    def list_charges(self): ...

    @route("POST", "/charges")
    def create_charge(self): ...

    @route("POST", "/logs", idempotency_key=False)
    def log(self): ...

    class refunds(Section):
        @route("POST", "/refunds")
        def create(self): ...

    class legacy(Section):
        idempotency_key = "X-Request-Id"

        @route("POST", "/old")
        def create(self): ...


def test_a_class_setting_keys_its_non_idempotent_routes(mock):
    payments = Payments(transport=mock)
    mock.respond(httpx.ReadTimeout("slow"), OK)
    payments.create_charge()
    assert len(mock.calls) == 2
    assert mock.calls[0].headers["Idempotency-Key"] == mock.calls[1].headers["Idempotency-Key"]
    mock.respond(OK)
    payments.list_charges()
    assert "Idempotency-Key" not in mock.last.headers


def test_sections_take_the_parents_key_or_their_own(mock):
    payments = Payments(transport=mock)
    mock.respond(OK, OK)
    payments.refunds.create()
    assert "Idempotency-Key" in mock.last.headers
    payments.legacy.create()
    assert "X-Request-Id" in mock.last.headers
    assert "Idempotency-Key" not in mock.last.headers


def test_a_route_can_turn_the_class_key_off(mock):
    mock.respond(httpx.ReadTimeout("slow"), OK)
    with pytest.raises(httpx.ReadTimeout):
        Payments(transport=mock).log()
    assert "Idempotency-Key" not in mock.last.headers


def test_graphql_routes_are_unchanged(mock):
    class Hub(Client):
        base_url = "https://hub.test"
        retries = Retries(attempts=3, sleep=0)
        viewer = graphql_route("query Viewer { viewer { id } }")
        star = graphql_route("mutation Star { star { id } }")

    hub = Hub(transport=mock)
    mock.respond(httpx.ReadTimeout("slow"), graphql_response(data={"viewer": None}))
    hub.viewer()
    assert len(mock.calls) == 2  # a query is idempotent, though it's a POST
    mock.calls.clear()
    mock.respond(httpx.ReadTimeout("slow"))
    with pytest.raises(httpx.ReadTimeout):
        hub.star()
    assert len(mock.calls) == 1


@pytest.mark.parametrize("value", [True, "", 3])
def test_a_bad_route_key_is_refused(value):
    from apiroute import RouteDefinitionError

    with pytest.raises(RouteDefinitionError, match="idempotency_key must be a header name"):

        class Bad(Client):
            @route("POST", "/x", idempotency_key=value)
            def x(self): ...


@pytest.mark.parametrize("value", ["", True])
def test_a_bad_class_key_is_refused(value):
    with pytest.raises(ValueError, match="idempotency_key must be a header name or None"):

        class Bad(Client):
            idempotency_key = value


class Trading(Client):
    """Like eBay's Trading API: every operation is a POST, and reads are named Get..."""

    base_url = "https://trading.test"
    retries = Retries(attempts=3, sleep=0)

    @route("POST", "/", operation="GetItem")
    def get_item(self): ...

    @route("POST", "/", operation="AddItem")
    def add_item(self): ...

    @route("GET", "/status", operation="Status")
    def status(self): ...

    class orders(Section):
        inherit = ("retries",)  # as generated sections do

        @route("POST", "/", operation="GetOrders")
        def get_orders(self): ...

    def idempotent(self, request):
        if request.operation == "Status":
            return False
        return True if request.operation.startswith("Get") else None


def attempts(call) -> int:
    mock = MockTransport()
    mock.respond(httpx.ReadTimeout("slow"), OK)
    try:
        call(mock)
    except httpx.ReadTimeout:
        pass
    return len(mock.calls)


@pytest.mark.parametrize(
    "call, count",
    [
        (lambda mock: Trading(transport=mock).get_item(), 2),  # POST the hook marks safe
        (lambda mock: Trading(transport=mock).add_item(), 1),  # POST it leaves to the route
        (lambda mock: Trading(transport=mock).status(), 1),  # GET it marks unsafe
        (lambda mock: Trading(transport=mock).orders.get_orders(), 2),  # a section uses the root's
        (lambda mock: asyncio.run(Trading(async_transport=mock.aio).aio.get_item()), 2),
    ],
)
def test_the_client_hook_decides_per_request(call, count):
    assert attempts(call) == count


def test_the_hook_sees_the_built_request():
    seen = []

    class Recording(Trading):
        def idempotent(self, request):
            seen.append((request.method, request.operation, request.url))
            return None

    mock = MockTransport()
    mock.respond(OK)
    Recording(transport=mock).get_item()
    assert seen == [("POST", "GetItem", "https://trading.test/")]


def test_a_keyed_request_is_retried_whatever_the_hook_says():
    class Keyed(Payments):
        def idempotent(self, request):
            return False

    mock = MockTransport()
    mock.respond(httpx.ReadTimeout("slow"), OK)
    Keyed(transport=mock).create_charge()
    assert len(mock.calls) == 2
