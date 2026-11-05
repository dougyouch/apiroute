import httpx
import pytest

from apiroute.polling import OperationFailed, Poll

REQUEST = httpx.Request("GET", "https://x.test/ops/1")


def response(status=200, json=None, **headers):
    names = {k.replace("_", "-"): v for k, v in headers.items()}
    return httpx.Response(status, json=json, headers=names, request=REQUEST)


def test_a_202_with_a_location_starts_polling():
    step = Poll(interval=2).first(response(202, Location="/ops/1"))
    assert (step.kind, step.url, step.delay) == ("wait", "/ops/1", 2)


@pytest.mark.parametrize("header", ["Operation-Location", "Azure-AsyncOperation"])
def test_operation_headers_start_polling_even_on_a_200_or_201(header):
    for status in (200, 201):
        assert Poll().first(response(status, **{header.replace("-", "_"): "/op"})).kind == "wait"


def test_a_201_with_a_location_is_a_created_resource_not_an_operation():
    assert Poll().first(response(201, Location="/things/1")).kind == "done"


def test_a_202_without_a_status_url_is_the_result():
    assert Poll().first(response(202)).kind == "done"


def test_the_first_header_found_wins():
    step = Poll().first(response(202, Location="/b", Operation_Location="/a"))
    assert step.url == "/a"


def test_retry_after_lengthens_the_wait():
    assert Poll(interval=1).first(response(202, Location="/o", Retry_After="5")).delay == 5
    assert Poll(interval=10).first(response(202, Location="/o", Retry_After="5")).delay == 10
    assert Poll(interval=1).first(response(202, Location="/o", Retry_After="soon")).delay == 1


@pytest.mark.parametrize("state", ["running", "InProgress", "queued", False])
def test_a_status_still_running_waits_again(state):
    step = Poll().next(response(json={"status": state}), "https://x.test/ops/1", "r")
    assert (step.kind, step.url) == ("wait", "https://x.test/ops/1")


@pytest.mark.parametrize("state", ["succeeded", "Completed", "DONE", True])
def test_a_succeeded_status_finishes(state):
    step = Poll().next(response(json={"status": state}), "u", "r")
    assert step.kind == "done"


@pytest.mark.parametrize("state", ["failed", "Canceled", "error"])
def test_a_failed_status_raises(state):
    body = {"status": state, "message": "disk full"}
    with pytest.raises(OperationFailed) as raised:
        Poll().next(response(json=body), "u", "export")
    assert raised.value.status == state
    assert raised.value.body == body
    assert str(raised.value) == f"export: the operation ended with status {state!r}"


def test_the_status_may_be_nested_and_named_otherwise():
    poll = Poll(status="operation.state", succeeded=("ready",), failed=("broken",))
    assert poll.next(response(json={"operation": {"state": "ready"}}), "u", "r").kind == "done"
    assert poll.next(response(json={"operation": {"state": "warming"}}), "u", "r").kind == "wait"
    with pytest.raises(OperationFailed):
        poll.next(response(json={"operation": {"state": "broken"}}), "u", "r")


def test_googles_done_and_error_fields():
    poll = Poll(status="done", result="response", error="error")
    assert poll.next(response(json={"done": False}), "u", "r").kind == "wait"
    done = response(json={"done": True, "response": {"id": 7}})
    assert poll.next(done, "u", "r").kind == "done"
    assert poll.decode(done) == {"id": 7}
    with pytest.raises(OperationFailed, match="ended with an error") as raised:
        poll.next(response(json={"done": True, "error": {"code": 3}}), "u", "r")
    assert raised.value.status is None


def test_a_body_without_a_status_is_the_result():
    assert Poll().next(response(json={"id": 1}), "u", "r").kind == "done"
    assert Poll().next(response(json=[1, 2]), "u", "r").kind == "done"
    assert Poll().next(httpx.Response(204, request=REQUEST), "u", "r").kind == "done"
    assert Poll(status=None).next(response(json={"status": "running"}), "u", "r").kind == "done"


def test_a_202_while_polling_waits_and_may_move_the_status_url():
    step = Poll().next(response(202, Location="/ops/1b", Retry_After="3"), "/ops/1", "r")
    assert (step.kind, step.url, step.delay) == ("wait", "/ops/1b", 3)
    assert Poll().next(response(202), "/ops/1", "r").url == "/ops/1"


def test_a_303_fetches_the_result():
    step = Poll().next(response(303, Location="/results/1"), "u", "r")
    assert (step.kind, step.url) == ("fetch", "/results/1")


def test_result_url_fetches_the_result_from_the_finished_body():
    poll = Poll(result_url="resourceLocation")
    finished = response(json={"status": "Succeeded", "resourceLocation": "/vms/1"})
    assert poll.next(finished, "u", "r").url == "/vms/1"
    assert poll.next(response(json={"status": "Succeeded"}), "u", "r").kind == "done"


def test_decode_reads_the_result_path_or_the_body():
    finished = response(json={"status": "done", "output": {"rows": 3}})
    assert Poll(result="output.rows").decode(finished) == 3
    assert Poll().decode(finished) == {"status": "done", "output": {"rows": 3}}
    assert Poll().decode(httpx.Response(200, content=b"not json", request=REQUEST)) is None


def test_running_statuses_take_the_newer_status_url():
    step = Poll().next(response(json={"status": "running"}, Location="/ops/2"), "/ops/1", "r")
    assert step.url == "/ops/2"


@pytest.mark.parametrize(
    ("kwargs", "problem"), [({"interval": -1}, "interval"), ({"timeout": 0}, "timeout")]
)
def test_invalid_settings(kwargs, problem):
    with pytest.raises(ValueError, match=problem):
        Poll(**kwargs)
