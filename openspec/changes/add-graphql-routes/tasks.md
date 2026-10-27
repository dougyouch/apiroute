## 1. Setup

- [x] 1.1 Add a `graphql = ["graphql-core>=3.2"]` extra to `pyproject.toml`, add graphql-core to the dev dependency group, and run `uv sync`
- [x] 1.2 Create the `src/apiroute/graphql/` package with an `__init__.py` docstring describing the module, mirroring `apiroute/soap/__init__.py`

## 2. Retry safety for non-idempotent routes

- [x] 2.1 Add `idempotent: bool = True` to `RouteSpec` and `RouteDefinition`, and pass it through `RouteCompiler`
- [x] 2.2 In `RouteExecutor._prepare`, wrap `should_retry` for non-idempotent routes so that `ReadTimeout`, `WriteTimeout`, `ReadError`, `WriteError` and `RemoteProtocolError` are never retried
- [x] 2.3 Tests in `tests/test_route_executor.py` (or the matching module): a non-idempotent route doesn't retry a read timeout but does retry `ConnectError`; idempotent routes are unchanged (sync and async)

## 3. Document parsing

- [x] 3.1 `GraphQLVariable` NamedTuple (name, type, required, has_default)
- [x] 3.2 `GraphQLDocument`: a tokenizer that skips strings, block strings and comments; reads operation type, name and variable definitions; supports shorthand `{...}` queries; and chooses an operation via `operation_name`
- [x] 3.3 Optional graphql-core syntax check, imported lazily inside `try`, which raises `ValueError` so `RouteCompiler` wraps it as `RouteDefinitionError`
- [x] 3.4 Tests in `tests/graphql/test_graphql_document.py`: named, anonymous and shorthand operations; several operations with and without `operation_name`; defaults and non-null types; comments and strings containing `$`/`(`; a syntax error with graphql-core installed; the same fixtures parsed by both parsers

## 4. Request and response

- [x] 4.1 `GraphQLBody`: a callable `body_format` with `encodes_empty = True` that drops `None` variables and returns the JSON `{"query", "operationName", "variables"}` body with `application/json`
- [x] 4.2 `GraphQLError(ApiRouteError)` with `.errors`, `.data`, `.codes` and `.response`, and a message built from the first error plus a count of the rest
- [x] 4.3 `GraphQLDecoder(operation, data_path, errors)`: rejects non-GraphQL bodies with `UnexpectedResponse`; raises `GraphQLError` on errors, or for `"partial"` logs and returns non-null data; turns a 400 without `errors` into `UnexpectedResponse`; unwraps the dotted path, returning `None` on a missing or null step
- [x] 4.4 Tests in `tests/graphql/test_graphql_body.py` and `tests/graphql/test_graphql_decoder.py` covering each scenario under "GraphQL errors raise GraphQLError", "Partial data can be accepted" and "Responses unwrap data"

## 5. graphql_route

- [x] 5.1 Variable binding: match variables to argument names (explicit `variables=`, then exact, then snake_case) and build the variables body template, with clear errors for unbound required variables and ambiguous matches
- [x] 5.2 `GraphQLRouteDecorator`: `__call__` for a def, and `generated_method` that builds a keyword-only signature from the variables (non-null without a default is required, the rest default to `None`)
- [x] 5.3 `graphql_route(...)`: builds the `RouteSpec` (POST, prefixed path, template body, `GraphQLBody`, `GraphQLDecoder`, `expected=(200, 400)`, Accept header merged with `headers`, operation name, `idempotent` from operation type unless overridden)
- [x] 5.4 Export `graphql_route` and `GraphQLError` from `apiroute` (lazily, so `import apiroute` doesn't import the graphql package) and from `apiroute.graphql`
- [x] 5.5 Tests in `tests/graphql/test_graphql_route.py` against `MockTransport`, covering every scenario under "Declare a GraphQL operation", "Requests follow the GraphQL-over-HTTP POST shape", "Method arguments map to declared variables", "Operation name identifies the request", the mutation retry scenarios, sections with `namespace()`, `compile_routes = "lazy"`, and async calls
- [x] 5.6 A test that `import apiroute` (and using a GraphQL route) works with graphql-core hidden from `sys.modules`/import

## 6. Testing helpers

- [x] 6.1 `apiroute.testing.graphql_response(data=None, errors=None, status=200, extensions=None)`, exported from `apiroute.testing`
- [x] 6.2 `MockCall.graphql_variables` property
- [x] 6.3 Tests in `tests/testing/` for operation-name matching across two operations, the `UnmatchedRequest` message, `graphql_response` bodies, and `graphql_variables`

## 7. Docs and release

- [x] 7.1 A README "GraphQL" section covering hand-written operations, variable mapping, `data=`, errors and `errors="partial"`, mutation retries, testing with `graphql_response`, and the `graphql` extra
- [x] 7.2 Add `graphql` to the extras sentence in AGENT.md's Rules, and `src/apiroute/graphql/` and `tests/graphql/` to the Layout table
- [ ] 7.3 Run `uv run ruff check .`, `uv run ruff format --check .` and `uv run pytest`, then commit as `feat: add graphql_route for hand-written GraphQL operations`
