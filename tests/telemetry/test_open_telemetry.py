import sys

import httpx
import pytest
from opentelemetry.trace import SpanKind, StatusCode

from apiroute import Client, Retries, UnexpectedResponse, route
from apiroute.telemetry import OpenTelemetry
from apiroute.testing.sleep_recording import recorded_sleeps


def api_for(provider, transport=None, async_transport=None, **telemetry_options):
    class Api(Client):
        base_url = "https://api.test:8443/v1"
        retries = Retries(attempts=2, sleep=0)
        telemetry = OpenTelemetry(provider, **telemetry_options)

        get_user = route("/users/{id}", query={"api_key": "secret"})
        list_users = route("/users", operation="listUsers")
        create_user = route("POST", "/users")
        events = route("/events", stream="sse")

    return Api(transport=transport, async_transport=async_transport)


def test_each_call_is_a_client_span(provider, exporter, transport, recorder):
    api_for(provider, transport).list_users()
    (span,) = exporter.get_finished_spans()
    assert span.name == "listUsers"
    assert span.kind == SpanKind.CLIENT
    assert span.instrumentation_scope.name == "apiroute"
    assert dict(span.attributes) == {
        "http.request.method": "GET",
        "url.full": "https://api.test:8443/v1/users",
        "server.address": "api.test",
        "server.port": 8443,
        "apiroute.operation": "listUsers",
        "http.response.status_code": 200,
    }
    assert span.status.status_code == StatusCode.UNSET


def test_the_url_is_redacted(provider, exporter, transport):
    api_for(provider, transport).get_user(id=1)
    (span,) = exporter.get_finished_spans()
    assert "secret" not in span.attributes["url.full"]
    assert span.name == "get_user"


def test_the_default_port_follows_the_scheme(provider, exporter, transport):
    class Plain(Client):
        base_url = "http://plain.test"
        telemetry = OpenTelemetry(provider)
        get_x = route("/x")

    Plain(transport=transport).get_x()
    assert exporter.get_finished_spans()[0].attributes["server.port"] == 80


def test_an_error_status_marks_the_span(provider, exporter, transport, recorder):
    recorder.respond(httpx.Response(404))
    with pytest.raises(UnexpectedResponse):
        api_for(provider, transport).list_users()
    (span,) = exporter.get_finished_spans()
    assert span.status.status_code == StatusCode.ERROR
    assert span.attributes["error.type"] == "404"
    assert span.attributes["http.response.status_code"] == 404


def test_each_attempt_is_its_own_span(provider, exporter, transport, recorder):
    recorder.respond(httpx.ConnectError("refused"), httpx.Response(200, json={}))
    with recorded_sleeps():
        api_for(provider, transport).list_users()
    failed, succeeded = exporter.get_finished_spans()
    assert failed.status.status_code == StatusCode.ERROR
    assert failed.attributes["error.type"] == "ConnectError"
    assert failed.events[0].name == "exception"
    assert succeeded.attributes["http.response.status_code"] == 200


def test_the_trace_context_is_sent(provider, exporter, transport, recorder):
    api_for(provider, transport).list_users()
    (span,) = exporter.get_finished_spans()
    traceparent = recorder.last.headers["traceparent"]
    assert traceparent.split("-")[1] == format(span.context.trace_id, "032x")
    assert traceparent.split("-")[2] == format(span.context.span_id, "016x")


def test_propagation_can_be_turned_off(provider, transport, recorder):
    api_for(provider, transport, propagate=False).list_users()
    assert "traceparent" not in recorder.last.headers


def test_spans_nest_under_the_callers_span(provider, exporter, transport):
    tracer = provider.get_tracer("app")
    with tracer.start_as_current_span("handle request") as parent:
        api_for(provider, transport).list_users()
    child = next(s for s in exporter.get_finished_spans() if s.name == "listUsers")
    assert child.parent.span_id == parent.get_span_context().span_id


def test_a_streams_span_ends_once_its_status_is_in(provider, exporter, transport, recorder):
    recorder.respond(httpx.Response(200, content=b"data: a\n\ndata: b\n\n"))
    events = api_for(provider, transport).events()
    assert [s.name for s in exporter.get_finished_spans()] == ["events"]
    assert [e.data for e in events] == ["a", "b"]
    assert "traceparent" in recorder.last.headers


def test_a_stream_that_fails_to_open_records_the_error(provider, exporter, transport, recorder):
    recorder.respond(httpx.ConnectError("x"), httpx.ConnectError("x"))
    with recorded_sleeps(), pytest.raises(httpx.ConnectError):
        api_for(provider, transport).events()
    assert [s.attributes["error.type"] for s in exporter.get_finished_spans()] == [
        "ConnectError"
    ] * 2


@pytest.mark.anyio
async def test_async_calls(provider, exporter, async_transport, recorder):
    api = api_for(provider, async_transport=async_transport)
    await api.aio.list_users()
    recorder.respond(httpx.Response(200, content=b"data: a\n\n"))
    events = await api.aio.events()
    assert [e.data async for e in events] == ["a"]
    assert [s.name for s in exporter.get_finished_spans()] == ["listUsers", "events"]
    assert "traceparent" in recorder.last.headers


@pytest.mark.anyio
async def test_async_errors(provider, exporter, async_transport, recorder):
    recorder.respond(httpx.Response(500))
    api = api_for(provider, async_transport=async_transport)
    with pytest.raises(UnexpectedResponse):
        await api.aio.list_users()
    recorder.respond(httpx.ConnectError("x"), httpx.ConnectError("x"))
    with recorded_sleeps(), pytest.raises(httpx.ConnectError):
        await api.aio.events()
    errors = [s.attributes["error.type"] for s in exporter.get_finished_spans()]
    assert errors == ["500", "ConnectError", "ConnectError"]


def test_without_opentelemetry_installed_the_error_says_what_to_install(monkeypatch):
    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    with pytest.raises(ImportError, match=r"apiroute\[otel\]"):
        OpenTelemetry()


def test_a_setting_that_isnt_telemetry_fails():
    with pytest.raises(ValueError, match="telemetry must be"):

        class Bad(Client):
            telemetry = "otel"
