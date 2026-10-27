from typing import Any

from apiroute.graphql.graphql_route_builder import GraphQLRouteBuilder
from apiroute.graphql.graphql_route_decorator import GraphQLRouteDecorator
from apiroute.graphql.graphql_route_options import GraphQLRouteOptions
from apiroute.namespace import current_prefix


def graphql_route(
    document: str,
    *,
    path: str = "/graphql",
    data: str | None = None,
    variables: dict[str, str] | None = None,
    errors: str = "raise",
    model: Any = None,
    headers: dict[str, Any] | None = None,
    timeout: float | None = None,
    operation_name: str | None = None,
    idempotent: bool | None = None,
    validate: bool = True,
    paginate: str | None = None,
    cursor: str = "after",
) -> GraphQLRouteDecorator:
    """Declares a GraphQL operation, written by hand, on a def or on its own:

        @graphql_route('''
            query Repo($owner: String!, $repoName: String!) {
              repository(owner: $owner, name: $repoName) { name stargazerCount }
            }
        ''', data="repository")
        def repo(self, owner: str, repo_name: str) -> Repository: ...

        viewer = graphql_route("query Viewer { viewer { login } }", data="viewer")

    It POSTs {"query", "operationName", "variables"} to path. Each variable is filled from the
    argument of the same name or its snake_case form, a client attribute, or the argument
    variables= maps it to ({"userID": "user_id"}); a None argument isn't sent. The response's
    data is returned, or the value at the dotted data path inside it, converted by model or
    the return annotation. errors="raise" raises GraphQLError when the response has errors;
    "partial" returns non-null data anyway and logs them. operation_name picks one operation
    of several, or names an anonymous one for hooks and mocks. A mutation isn't retried once
    the request may have reached the server, unless idempotent=True. When the class (or one
    enclosing its section) sets graphql_schema, the document is validated against it as the
    route is compiled; validate=False skips that for this route.

    paginate="repository.issues" makes the method return an iterator over that Relay
    connection's items (its nodes, or each edge's node), across pages: each page is requested
    as iteration reaches it, with the last pageInfo.endCursor as the $after variable (cursor=
    names another). Items are converted by model= or an Iterator[Item] return annotation.
    """
    options = GraphQLRouteOptions(
        document=document,
        path=current_prefix() + _absolute(path),
        data=data,
        variables=dict(variables or {}),
        errors=errors,
        model=model,
        headers=headers,
        timeout=timeout,
        operation_name=operation_name,
        idempotent=idempotent,
        validate=validate,
        paginate=paginate,
        cursor=cursor,
    )
    return GraphQLRouteDecorator(GraphQLRouteBuilder(options))


def _absolute(path: str) -> str:
    return path if path == "" or path.startswith("/") else f"/{path}"
