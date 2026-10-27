from __future__ import annotations

import asyncio
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from apiroute import Client, GraphQLError, RouteDefinitionError, graphql_route
from apiroute.testing import MockTransport, graphql_response

ISSUES = """
query Issues($owner: String!, $first: Int = 2, $after: String) {
  repository(owner: $owner, name: "x") {
    issues(first: $first, after: $after) {
      pageInfo { hasNextPage endCursor }
      nodes { number title }
    }
  }
}
"""


@dataclass
class Issue:
    number: int
    title: str


def page(numbers, cursor=None, more=False):
    nodes = [{"number": n, "title": f"#{n}"} for n in numbers]
    issues = {"pageInfo": {"hasNextPage": more, "endCursor": cursor}, "nodes": nodes}
    return graphql_response(data={"repository": {"issues": issues}})


class Hub(Client):
    base_url = "https://api.hub.test"

    @graphql_route(ISSUES, paginate="repository.issues")
    def issues(self, owner: str) -> Iterator[Issue]: ...

    @graphql_route(ISSUES, paginate="repository.issues")
    def issues_from(self, owner: str, after: str | None = None) -> Iterator[Issue]: ...

    raw_issues = graphql_route(ISSUES, paginate="repository.issues")


@pytest.fixture
def mock():
    return MockTransport()


@pytest.fixture
def hub(mock):
    return Hub(transport=mock, async_transport=mock.aio)


def test_iterates_every_page_as_typed_items(hub, mock):
    mock.respond(page([1, 2], "c1", True), page([3, 4], "c2", True), page([5]))
    assert [issue.number for issue in hub.issues("acme")] == [1, 2, 3, 4, 5]
    assert [call.graphql_variables.get("after") for call in mock.calls] == [None, "c1", "c2"]
    assert all(call.operation == "Issues" for call in mock.calls)


def test_items_are_typed(hub, mock):
    mock.respond(page([1]))
    assert list(hub.issues("acme")) == [Issue(1, "#1")]


def test_a_generated_signature_yields_dicts(hub, mock):
    mock.respond(page([1], "c1", True), page([2]))
    assert list(hub.raw_issues(owner="acme", first=1)) == [
        {"number": 1, "title": "#1"},
        {"number": 2, "title": "#2"},
    ]
    assert [call.graphql_variables for call in mock.calls] == [
        {"owner": "acme", "first": 1},
        {"owner": "acme", "first": 1, "after": "c1"},
    ]


def test_nothing_is_sent_until_iteration(hub, mock):
    items = hub.issues("acme")
    assert mock.calls == []
    mock.respond(page([1, 2], "c1", True))
    assert next(items).number == 1
    assert len(mock.calls) == 1


def test_a_graphql_error_on_a_later_page(hub, mock):
    mock.respond(page([1], "c1", True), graphql_response(errors=[{"message": "rate limited"}]))
    items = hub.issues("acme")
    assert next(items).number == 1
    with pytest.raises(GraphQLError, match="rate limited"):
        next(items)


def test_async_iteration(hub, mock):
    mock.respond(page([1], "c1", True), page([2]))

    async def collect():
        return [issue.number async for issue in hub.aio.issues("acme")]

    assert asyncio.run(collect()) == [1, 2]


def test_model_converts_items_of_a_route_without_a_def(mock):
    class Api(Client):
        base_url = "https://x.test"
        issues = graphql_route(ISSUES, paginate="repository.issues", model=Issue)

    mock.respond(page([7]))
    assert list(Api(transport=mock).issues(owner="o")) == [Issue(7, "#7")]


def test_another_cursor_variable(mock):
    class Api(Client):
        base_url = "https://x.test"
        issues = graphql_route(
            ISSUES.replace("$after", "$cursor"), paginate="repository.issues", cursor="cursor"
        )

    mock.respond(page([1], "c1", True), page([2]))
    assert len(list(Api(transport=mock).issues(owner="o"))) == 2
    assert mock.calls[1].graphql_variables["cursor"] == "c1"


def test_pages_go_through_hooks(mock):
    seen = []

    class Api(Hub):
        def on_request(self, request):
            seen.append(request.operation)

    mock.respond(page([1], "c1", True), page([2]))
    list(Api(transport=mock).issues("o"))
    assert seen == ["Issues", "Issues"]


@pytest.mark.parametrize(
    "declare, message",
    [
        (
            lambda: graphql_route("query Q { viewer { id } }", paginate="viewer.x"),
            r"declare \$after",
        ),
        (
            lambda: graphql_route(ISSUES, paginate="repository.issues", data="repository"),
            "can't take data=",
        ),
    ],
)
def test_misconfigured_routes_fail_when_the_class_is_created(declare, message):
    with pytest.raises(RouteDefinitionError, match=message):

        class Api(Client):
            op = declare()


def test_a_method_without_a_cursor_parameter_still_pages(hub, mock):
    mock.respond(page([1], "c1", True), page([2]))
    assert [issue.number for issue in hub.issues("acme")] == [1, 2]
    assert [call.graphql_variables for call in mock.calls] == [
        {"owner": "acme"},
        {"owner": "acme", "after": "c1"},
    ]


def test_a_cursor_parameter_starts_mid_list(hub, mock):
    mock.respond(page([6], "c6", True), page([7]))
    assert [issue.number for issue in hub.issues_from("acme", after="c5")] == [6, 7]
    assert [call.graphql_variables["after"] for call in mock.calls] == ["c5", "c6"]


def test_with_options_apply_to_every_page(hub, mock):
    mock.respond(page([1], "c1", True), page([2]))
    list(hub.with_options(headers={"X-Trace": "t"}).issues("acme"))
    assert [call.headers["X-Trace"] for call in mock.calls] == ["t", "t"]
