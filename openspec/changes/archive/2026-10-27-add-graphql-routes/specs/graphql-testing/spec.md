## ADDED Requirements

### Requirement: Mocks match GraphQL operations by name
`MockTransport.on(operation=...)` SHALL match GraphQL route calls by their operation name. This lets tests answer different operations differently even though they all share one method and path.

#### Scenario: Two operations on one endpoint
- **WHEN** a test registers `mock.on(operation="Viewer").respond(a)` and `mock.on(operation="Repo").respond(b)`, then calls `client.repo(...)` and `client.viewer()`
- **THEN** `repo` receives `b` and `viewer` receives `a`

#### Scenario: Unmatched operation
- **WHEN** a GraphQL route is called and no route, queued response or handler answers it
- **THEN** `UnmatchedRequest` is raised, and its message names the operation

### Requirement: Build GraphQL responses for tests
`apiroute.testing` SHALL provide `graphql_response(data=None, errors=None, status=200, extensions=None)`. It returns an `httpx.Response` whose JSON body contains `data` when given (including an explicit `None` when errors are given), `errors` when given, and `extensions` when given. It SHALL be usable anywhere `MockTransport` accepts a response.

#### Scenario: Data response
- **WHEN** a test responds with `graphql_response(data={"viewer": {"login": "a"}})`
- **THEN** a route with `data="viewer"` returns `{"login": "a"}`

#### Scenario: Error response
- **WHEN** a test responds with `graphql_response(errors=[{"message": "nope"}])`
- **THEN** the body is `{"data": null, "errors": [{"message": "nope"}]}` and the route raises `GraphQLError`

### Requirement: Recorded calls expose GraphQL variables
A `MockCall` for a GraphQL request SHALL let tests read the sent `operationName` and `variables` without parsing the body by hand.

#### Scenario: Asserting variables
- **WHEN** `client.repo(owner="a", repo_name="b")` is called against a `MockTransport`
- **THEN** `mock.last.graphql_variables == {"owner": "a", "repoName": "b"}` and `mock.last.operation == "Repo"`
