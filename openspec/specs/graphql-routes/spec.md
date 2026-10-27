# graphql-routes Specification

## Purpose
TBD - created by archiving change add-graphql-routes. Update Purpose after archive.
## Requirements
### Requirement: Declare a GraphQL operation as a client method
The library SHALL provide `graphql_route(document, ...)`, exported from `apiroute`, which declares one GraphQL operation as a method on a `Client` or `Section`. It SHALL work both on a `def` and as a bare class attribute assignment.

#### Scenario: Decorating a def
- **WHEN** a client defines `@graphql_route("query Viewer { viewer { login } }")` on `def viewer(self) -> dict: ...`
- **THEN** calling `client.viewer()` sends one request and returns the response's `data`

#### Scenario: Bare assignment generates the signature
- **WHEN** a client defines `repo = graphql_route("query Repo($owner: String!, $repoName: String!, $first: Int) { ... }")`
- **THEN** `client.repo` takes keyword-only arguments `owner` and `repo_name` (required) and `first` (defaulting to `None`)

#### Scenario: Async clients
- **WHEN** a GraphQL route is called through the client's async interface
- **THEN** it sends the same request and returns the same result as the sync call

### Requirement: Requests follow the GraphQL-over-HTTP POST shape
A GraphQL route SHALL send a POST to its `path` (default `/graphql`, under any `namespace()` or section prefix). The body SHALL be JSON with `query` (the document as written), `variables` (an object) and `operationName` (when the operation is named). It SHALL send `Content-Type: application/json` and `Accept: application/graphql-response+json, application/json`, plus the class's headers and the route's `headers`.

#### Scenario: Request body
- **WHEN** `client.repo(owner="a", repo_name="b")` is called
- **THEN** the request is `POST {base_url}/graphql` with JSON body `{"query": <document>, "operationName": "Repo", "variables": {"owner": "a", "repoName": "b"}}`

#### Scenario: Custom path inside a section
- **WHEN** a section with prefix `/v4` declares `graphql_route(doc, path="/graphql")`
- **THEN** the request goes to `{base_url}/v4/graphql`

#### Scenario: Operation without variables
- **WHEN** an operation that declares no variables is called
- **THEN** the body still contains `query` and `"variables": {}`

### Requirement: Method arguments map to declared variables
Each declared variable SHALL be bound to:
- the argument named in `variables=` for it, else
- an argument with the same name, else
- an argument whose snake_case form equals the variable's snake_case form, else
- a client attribute of either name.

Arguments with the value `None` SHALL be omitted from `variables`. The class definition SHALL fail with `RouteDefinitionError` when a required variable (non-null type, no default) is bound to nothing, or when an argument binds to no variable and isn't marked `Header` or `Result`.

#### Scenario: camelCase variable from a snake_case argument
- **WHEN** the document declares `$repoName: String!` and the method has a `repo_name` argument
- **THEN** the argument's value is sent as `variables.repoName`

#### Scenario: Explicit mapping
- **WHEN** `graphql_route(doc, variables={"userID": "user_id"})` is used and the method has a `user_id` argument
- **THEN** the argument's value is sent as `variables.userID`

#### Scenario: Missing required variable
- **WHEN** the document declares `$owner: String!` and neither the method nor the client provides `owner`
- **THEN** defining the class raises `RouteDefinitionError` naming the route and `$owner`

#### Scenario: Unused argument
- **WHEN** the method has an argument `extra` that matches no declared variable and has no `Header` or `Result` marker
- **THEN** defining the class raises `RouteDefinitionError`

#### Scenario: None is omitted
- **WHEN** `client.repo(owner="a", repo_name="b", first=None)` is called
- **THEN** `variables` has no `first` key

### Requirement: Operation name identifies the request
A GraphQL route's `RequestSpec.operation` SHALL be the operation's name: the document's name for a named operation, else `operation_name=`, else the method name. A document with more than one operation SHALL require `operation_name=` to pick one, or the class definition fails with `RouteDefinitionError`.

#### Scenario: Hooks see the operation name
- **WHEN** a named operation `Viewer` is called on a client that overrides `on_request`
- **THEN** `on_request` receives a `RequestSpec` whose `operation` is `"Viewer"`

#### Scenario: Several operations without a choice
- **WHEN** a document defines `query A { ... }` and `query B { ... }` and no `operation_name` is given
- **THEN** defining the class raises `RouteDefinitionError`

### Requirement: Responses unwrap data and convert to models
A successful GraphQL response SHALL return its `data` object. When `data="a.b"` is given, it SHALL return the value at that dotted path inside `data`, or `None` when any step is missing or null. The result SHALL then be converted by `model=` or the method's return annotation, as with `@route`.

#### Scenario: Unwrapping a path
- **WHEN** a route with `data="viewer.repositories.nodes"` receives `{"data": {"viewer": {"repositories": {"nodes": [{"name": "x"}]}}}}`
- **THEN** it returns `[{"name": "x"}]`

#### Scenario: Null along the path
- **WHEN** a route with `data="repository.owner"` receives `{"data": {"repository": null}}`
- **THEN** it returns `None`

#### Scenario: Model conversion
- **WHEN** a route annotated `-> Viewer` (a dataclass or pydantic model) receives `{"data": {"viewer": {"login": "a"}}}` with `data="viewer"`
- **THEN** it returns a `Viewer` with `login == "a"`

### Requirement: GraphQL errors raise GraphQLError
When a response's JSON has a non-empty `errors` array, the route SHALL raise `GraphQLError`, a subclass of `ApiRouteError`. It SHALL expose `.errors` (the list as received), `.data` (the `data` value, possibly partial, or `None`), `.codes` (the `extensions.code` values present) and `.response`. Its message SHALL include the first error's `message`. This applies to HTTP 200 and 400 responses. Other non-2xx statuses SHALL raise `UnexpectedResponse`, as on `@route`.

#### Scenario: Errors on a 200
- **WHEN** a response is `200 {"data": {"viewer": null}, "errors": [{"message": "Not allowed", "extensions": {"code": "FORBIDDEN"}}]}`
- **THEN** the call raises `GraphQLError` with `.codes == ["FORBIDDEN"]` and `.data == {"viewer": null}`

#### Scenario: Errors on a 400
- **WHEN** a response is `400 {"errors": [{"message": "Syntax Error"}]}`
- **THEN** the call raises `GraphQLError`

#### Scenario: 400 without a GraphQL body
- **WHEN** a response is `400` with a body that has no `errors`
- **THEN** the call raises `UnexpectedResponse`

#### Scenario: Server error
- **WHEN** a response is `502`
- **THEN** the call raises `UnexpectedResponse`

#### Scenario: Not a GraphQL response
- **WHEN** a 200 response body is not a JSON object with `data` or `errors`
- **THEN** the call raises `UnexpectedResponse`

### Requirement: Partial data can be accepted
With `errors="partial"`, a response that has both errors and non-null `data` SHALL return the unwrapped data and log the errors at WARNING level. A response with errors and null `data` SHALL still raise `GraphQLError`.

#### Scenario: Partial success
- **WHEN** a route with `errors="partial"` receives `{"data": {"a": 1, "b": null}, "errors": [{"message": "b failed", "path": ["b"]}]}`
- **THEN** it returns `{"a": 1, "b": null}` and logs a warning naming the operation and `b failed`

#### Scenario: Total failure
- **WHEN** a route with `errors="partial"` receives `{"data": null, "errors": [{"message": "boom"}]}`
- **THEN** it raises `GraphQLError`

### Requirement: Mutations are not retried after the request may have reached the server
Routes declared from a `mutation` operation SHALL be non-idempotent unless `idempotent=True` is passed. For a non-idempotent route, errors that may occur after the request was sent SHALL NOT be retried, whatever `should_retry` returns. These are read and write timeouts, read and write errors, and remote protocol errors. Errors before sending (connect errors, connect timeouts, pool timeouts) and HTTP responses SHALL still be offered to `should_retry`. Query routes SHALL be idempotent, although they're sent as POST. `@route` methods SHALL follow the route-idempotency rules: idempotent by default for `GET`, `HEAD` and `OPTIONS` only.

#### Scenario: Mutation read timeout
- **WHEN** a client with `retries = Retries(attempts=3)` calls a mutation route and the transport raises `httpx.ReadTimeout`
- **THEN** the call raises after one attempt

#### Scenario: Mutation connect error
- **WHEN** the same client calls the mutation and the first attempt raises `httpx.ConnectError`
- **THEN** the request is retried

#### Scenario: Query read timeout
- **WHEN** the same client calls a query route and the first attempt raises `httpx.ReadTimeout`
- **THEN** the request is retried

#### Scenario: Mutation explicitly idempotent
- **WHEN** a mutation route is declared with `idempotent=True` and the first attempt raises `httpx.ReadTimeout`
- **THEN** the request is retried

### Requirement: Documents are checked when the class is defined
The library SHALL read each document's operation type, name and variable definitions without third-party packages. When `graphql-core` is installed (the `graphql` extra), it SHALL also parse the document with it, and turn a syntax error into `RouteDefinitionError` when the class is defined (or on first use with `compile_routes = "lazy"`). Without `graphql-core`, the library SHALL work and SHALL NOT import it.

#### Scenario: Syntax error with graphql-core
- **WHEN** graphql-core is installed and a route's document is `query Viewer { viewer { login }` (unbalanced)
- **THEN** defining the class raises `RouteDefinitionError` naming the route

#### Scenario: No graphql-core
- **WHEN** graphql-core is not installed
- **THEN** a well-formed GraphQL route works, and `import apiroute` does not import `graphql`

#### Scenario: Strings and comments don't confuse the scanner
- **WHEN** a document has a `# ($fake: Int)` comment and a `"$x("` string argument before its selection set
- **THEN** only the real variable definitions are read

