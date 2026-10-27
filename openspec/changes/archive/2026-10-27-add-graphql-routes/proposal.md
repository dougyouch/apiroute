## Why

apiroute covers REST (`@route`, OpenAPI codegen) and SOAP (WSDL codegen), but a GraphQL API today means hand-building `{"query", "variables"}` bodies, unwrapping `data`, and checking `errors` yourself in every method. Many APIs that apiroute users already call (GitHub, Shopify, Linear) offer GraphQL alongside REST, so one client class with REST routes and GraphQL operations, sharing auth, retries, hooks and test helpers, would fill a real gap.

GraphQL can't follow the OpenAPI model of generating a call per endpoint: the caller picks the response shape, so a generator can't choose a selection set. The approach that works (genqlient, ariadne-codegen, graphql-codegen) puts the operation document first: the user writes the query and the library handles the plumbing. This change adds that runtime layer. Codegen can be added later on top of it.

## What Changes

- New `graphql_route(document, ...)` decorator, exported from `apiroute`. It declares one GraphQL operation as a client method, either on a `def` or as a bare assignment whose signature is generated from the operation's variables.
- Method arguments become GraphQL variables. `repo_name` maps to `$repoName` automatically, `variables=` gives an explicit mapping, and a mismatch between arguments and declared variables is a `RouteDefinitionError` when the class is defined.
- The request is a POST to `path` (default `/graphql`, under any section prefix) with a JSON `{"query", "operationName", "variables"}` body. Variables whose value is `None` are omitted, so defaults in the document apply.
- The operation name is sent as `operationName` and becomes `RequestSpec.operation`. This means `on_request`/`on_response` hooks and `MockTransport.on(operation=...)` can tell operations apart, even though they all share one URL.
- New `GraphQLError(ApiRouteError)`, raised when a response has a non-empty `errors` array. It carries `.errors`, `.data` (any partial data) and `.response`. Passing `errors="partial"` returns partial data instead of raising, as long as `data` isn't null.
- `data="viewer.repositories"` unwraps a path inside `data` before conversion to a model (from `model=` or the return annotation).
- Retry safety: `query` operations are retried like any other route. `mutation` operations are not retried after a failure that may have reached the server (read timeouts, dropped connections). Failures before the request was sent are still retried.
- Optional `graphql` extra (`graphql-core`). When it's installed, documents are parsed with it when the class is defined, so syntax errors show up early. Without it, a built-in scanner reads the operation type, name and variables.
- `apiroute.testing.graphql_response(data=..., errors=...)` builds GraphQL responses for `MockTransport`.

Out of scope, each a candidate for a later change: an `apiroute generate graphql` code generator and schema validation, Relay pagination helpers, persisted queries, file uploads, subscriptions, and a Python query-builder DSL.

## Capabilities

### New Capabilities
- `graphql-routes`: declaring GraphQL operations as client methods. Covers request building, mapping arguments to variables, unwrapping responses, handling GraphQL errors, retry safety for mutations, and optional parsing with graphql-core.
- `graphql-testing`: test support for GraphQL routes in `apiroute.testing`, namely matching mocks by operation name and the `graphql_response` builder.

### Modified Capabilities
<!-- None: openspec/specs/ has no existing specs. -->

## Impact

- **New modules:** `src/apiroute/graphql/` (`graphql_route`, `GraphQLBody`, `GraphQLDecoder`, `GraphQLDocument`, `GraphQLError`) and `src/apiroute/testing/graphql_response.py`.
- **Changed modules:**
  - `RouteSpec` gets an `idempotent` field.
  - `RetryPolicy`/`RouteExecutor` respect it for errors that may have reached the server.
  - `RouteDefinition`/`RouteCompiler` carry it through.
  - `apiroute/__init__.py` and lazy exports are updated.
- **Dependencies:** a new optional `graphql` extra (`graphql-core>=3.2`) in `pyproject.toml`. The runtime still depends only on `httpx`.
- **Docs:** a README section on GraphQL, and the extras list in AGENT.md.
- **Compatibility:** `@route` and the generated REST and SOAP clients behave the same, because `idempotent` defaults to `True`. The emitters don't change. Release type: `feat:` (minor).
