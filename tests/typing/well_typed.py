# mypy: disable-error-code="empty-body"
"""Checked by mypy in test_static_types.py, never run: what type checkers see for callers."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from typing_extensions import assert_type

from apiroute import FROM_CLIENT, FROM_RESPONSE, Client, Section, graphql_route, route
from apiroute.typed_client import TypedClient


@dataclass
class Issue:
    number: int


class Api(Client):
    @route("/users/{name}")
    def get_user(self, name: str, *, full: bool = False) -> dict[str, int]: ...

    @route("POST", "/users", idempotent=True)
    def create_user(self, body: dict[str, Any]) -> None: ...

    get_raw = route("/raw/:id")  # no def: its signature is made when the class is

    @graphql_route(
        "query Q($after: String) { a { pageInfo { hasNextPage endCursor } nodes { number } } }",
        paginate="a",
    )
    def issues(self) -> Iterator[Issue]: ...

    viewer = graphql_route("query Viewer { viewer { login } }")

    class things(Section):
        @route("/things")
        def list(self, kind: str | None = None) -> list[str]: ...


class Views(TypedClient):
    def get(self, name: str) -> Issue:
        return self._call("get", "Issue", name=name)


api = Api()
assert_type(api.get_user("octo"), dict[str, int])
assert_type(api.get_user("octo", full=True), dict[str, int])
assert_type(api.create_user({"name": "x"}), None)
for issue in api.issues():
    assert_type(issue, Issue)

# routes without a def take anything, and give Any
api.get_raw(id=1, extra="ok")
api.viewer(anything=True)

# a nested section: typed by pyright; to mypy its routes are Any, and never an error
api.things.list()
api.things.list(kind="open")

views = Views(api)
assert_type(views.get("x"), Issue)
assert_type(views.with_options(timeout=5), Views)
views.aio.get("x")  # the async view is Any


class Hooks(Client):
    org = "acme"

    @route("/users/{name}")
    def login(self, name: str, *, data: dict[str, str] = FROM_RESPONSE) -> str:
        return data["login"]

    @route("/orgs/{org}/repos")
    def repos(self, org: str = FROM_CLIENT, page: int = 1) -> list[dict[str, Any]]: ...


hooks = Hooks()
assert_type(hooks.login("octo"), str)  # FROM_RESPONSE isn't asked of callers
assert_type(hooks.repos(), list[dict[str, Any]])  # FROM_CLIENT is a valid str default
