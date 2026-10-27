## Context

A route today is a `RouteSpec`. `RouteCompiler` checks it against the method signature to produce a `RouteDefinition`, which `RequestBuilder`, `RouteExecutor` and `ResponseReader` then run. SOAP showed that a whole protocol can sit on top of `@route` without touching the core:

- `SoapBody` is a callable `body_format` that wraps the rendered body (`encodes_empty = True`, and it returns its own Content-Type).
- `SoapDecoder` is a `decoder` that replaces JSON parsing and raises `SoapFault`.
- The WSDL generator sets `operation=` so hooks and mocks can tell calls apart on a single URL.

GraphQL has the same shape: one URL, a POST, a JSON envelope in, and an envelope with `data`/`errors` out. Most of this change follows the SOAP pattern. Two pieces are new:
1. Mapping variables from the operation document to method arguments.
2. Retry safety for mutations. Today `Client.should_retry` retries `RETRYABLE_ERRORS` (timeouts, network and protocol errors) on any route, and it only sees `(error, attempt)`, not the route.

Constraints from AGENT.md: Python 3.10+, one class per file, the runtime depends only on httpx with optional libraries imported lazily, and ruff with E/F/I/B/UP at line length 100.

## Goals / Non-Goals

**Goals:**
- `graphql_route` declares an operation from a hand-written document, on a `def` or as a bare assignment, with the same signature checks `@route` gets when the class is defined.
- GraphQL errors raise a typed exception that keeps partial data. Successful responses unwrap to the useful node and convert to models as REST routes do.
- Mutations are not silently re-executed after a failure that may have reached the server.
- Mocks can tell GraphQL operations apart.
- No new required dependency. graphql-core is an optional extra.

**Non-Goals:**
- Code generation (`apiroute generate graphql`), introspection, and schema validation of documents.
- Relay pagination, persisted queries (APQ), multipart uploads, subscriptions (websocket/SSE), batching, and a query-builder DSL.
- Changing retry behavior for existing `@route` methods. `idempotent` stays internal to `RouteSpec` for now (see Open Questions).

## Decisions

### 1. `graphql_route` builds a `RouteSpec`, with no parallel route machinery

`graphql_route(document, *, path="/graphql", data=None, variables=None, errors="raise", model=None, headers=None, timeout=None, operation_name=None)` parses the document into a `GraphQLDocument` and returns a `GraphQLRouteDecorator` that wraps a `RouteSpec`:
- `method="POST"`, with `path` under `current_prefix()` so `namespace()` and sections work.
- `body` is a **template of the variables only**: `{"repoName": "{repo_name}", ...}`. The existing `ValueTemplate` and `RouteCompiler` binding then check that every argument is used and resolve client-attribute placeholders (`FROM_CLIENT`) for free.
- `body_format=GraphQLBody(document)`, which takes the rendered variables dict and returns `({"query", "operationName", "variables"} as JSON, "application/json")`. `encodes_empty = True`, so an operation without variables still sends a body.
- `decoder=GraphQLDecoder(data_path, errors)`.
- `expected=(200, 400)`. Under the GraphQL-over-HTTP spec, servers that use `application/graphql-response+json` return 400 for request errors with an `errors` body. The decoder turns those into `GraphQLError`. Other statuses (401, 403, 5xx) remain `UnexpectedResponse`, as on any route.
- `headers` merged with `{"Accept": "application/graphql-response+json, application/json"}`.
- `operation=` the operation name, so `RequestSpec.operation` and `MockTransport.on(operation=...)` work unchanged.
- `idempotent = document.operation_type != "mutation"`.

*Alternative:* a `GraphQLRouteMethod` with its own executor. It was rejected because it would duplicate retries, hooks, async, sections and lazy compilation, and those would then drift apart.

*Why the query isn't in the template:* GraphQL selection sets are full of `{` and `}`, which `ValueTemplate` would read as placeholders. Keeping the document in `GraphQLBody` sidesteps any escaping.

### 2. Variables are matched to arguments by name, with automatic camelCase

`GraphQLDocument` lists the declared variables (name, type, whether required, whether there's a default). Each variable is matched to an argument as follows:
1. An explicit `variables={"repoName": "repo"}` entry (variable → argument name).
2. Otherwise, an argument with the same name.
3. Otherwise, an argument whose snake_case form matches (`repoName` ↔ `repo_name`).

When the class is defined, a `RouteDefinitionError` is raised for:
- a required variable (`Type!` with no default) that matches no argument and no client attribute;
- an argument that matches no variable and isn't a `Header` or `Result` (this already comes from `RouteCompiler._bind_arguments`, because the argument isn't in the body template).

For a bare assignment (`viewer = graphql_route("""...""")`), `GraphQLRouteDecorator.generated_method` builds the signature from the variables rather than reusing `GeneratedSignature`. That way each argument is snake_case and keyword-only, a non-null variable without a default is required, and the rest default to `None`. `GeneratedSignature` would make every placeholder required.

*Alternative:* require exact names (`def repo(self, repoName)`). Rejected because it pushes camelCase into Python signatures, and ruff's naming rules would flag it in downstream code.

### 3. `None` variables are omitted from the request

`GraphQLBody` drops keys whose value is `None` before encoding. In GraphQL, an omitted variable takes the document's default, while an explicit `null` overrides it. Python's `= None` almost always means "not given", so omitting is the safer mapping. An explicit null can still be sent by passing `variables` through a `Body` argument (see Open Questions).

### 4. Error handling: `GraphQLError` with partial data; `errors="partial"` as an opt-out

`GraphQLDecoder` handles responses as follows:
- A body that isn't JSON, or isn't an object with `data` and/or `errors`, raises `UnexpectedResponse`.
- A non-empty `errors` array, with `errors="raise"` (the default), raises `GraphQLError(errors, data, response)`. The message is built from the first error's `message` and `path`, plus a count of the rest. `.codes` lists `extensions.code` values so callers can branch on them, for example `THROTTLED`.
- A non-empty `errors` array with `errors="partial"` and non-null `data`: the errors are logged at WARNING level and the unwrapped data is returned. If `data` is null, it still raises.
- `data` is then unwrapped along the dotted `data=` path. A missing key or a null along the way returns `None`, because GraphQL nulls propagate upward and a null parent is a legitimate answer.

Model conversion is unchanged: `ResponseReader` applies the converter to whatever the decoder returns.

*Alternative:* return a `GraphQLResult(data, errors)` wrapper. Rejected as the default because it breaks `-> Viewer` return annotations. Callers who need both can catch `GraphQLError` and read `.data`.

`GraphQLError` is not in `RETRYABLE_ERRORS`. Retrying a throttled query is the user's choice, made in `should_retry`, as with a 503.

### 5. Retry safety: `RouteSpec.idempotent`

`RouteSpec` and `RouteDefinition` gain `idempotent: bool = True`. When it's `False`, `RouteExecutor` wraps the client's `should_retry` so that errors which may have reached the server are never retried. These are `httpx.ReadTimeout`, `httpx.WriteTimeout`, `httpx.ReadError`, `httpx.WriteError` and `httpx.RemoteProtocolError`. Errors raised before anything was sent are still offered to `should_retry`: `httpx.ConnectError`, `httpx.ConnectTimeout` and `httpx.PoolTimeout`. So are HTTP responses such as 429 or 503, which the user opts into.

`RetryPolicy` stays the same: it receives the wrapped predicate.

*Alternative:* pass the route to `should_retry`. Rejected because it changes a public override signature and breaks subclasses.

### 6. Document parsing: a built-in scanner, with graphql-core as an optional check

`GraphQLDocument` uses a small tokenizer that skips strings, block strings and `#` comments. It reads the top-level operation definitions (type, name, variable definitions) and ignores selection sets and fragments. The rules:
- A document with several operations needs `operation_name=`.
- An anonymous operation is labelled by `operation_name=`, else by the method's name, for `RequestSpec.operation`. No `operationName` is sent in that case.
- A shorthand `{ ... }` document is a query.

If `graphql-core` is importable, `GraphQLDocument` also calls `graphql.parse(document)` when the class is defined, so a syntax error becomes a `RouteDefinitionError` at import time. The import is lazy, inside a `try`, following the pydantic and defusedxml pattern.

*Alternative:* require graphql-core. Rejected because it would add a runtime dependency for something a ~100-line scanner covers. Full validation needs a schema anyway, which belongs to a later codegen change.

### 7. Module layout

`src/apiroute/graphql/` holds one class per file:
- `graphql_route.py` (the function) and `graphql_route_options.py` (NamedTuple of its arguments)
- `graphql_route_decorator.py` (a `RouteDecorator` subclass, so the router's bare-assignment handling picks it up)
- `graphql_route_method.py` (a `RouteMethod` that builds its spec at compile time through a new `RouteMethod._spec_for(owner, name)` hook, since binding needs the method's parameters and the class's attributes)
- `graphql_route_builder.py` (options → `RouteSpec`, and the generated stub signature)
- `graphql_variable_binder.py` and `snake_case.py`
- `graphql_tokens.py`, `graphql_document.py`, `graphql_operation.py` and `graphql_variable.py` (NamedTuples)
- `graphql_syntax_check.py` (the lazy graphql-core import)
- `graphql_body.py`, `graphql_decoder.py` and `graphql_error.py`

The check whether a class declares a name moves out of `GeneratedSignature` into `apiroute/class_declaration.py`, which both use. The retry wrapper is `apiroute/unsent_retry_filter.py`.

`graphql_route` and `GraphQLError` are re-exported from `apiroute`. Importing them doesn't import graphql-core, which is imported only when a document is checked.

The testing helper `graphql_response(data=..., errors=None, status=200, extensions=None)` goes in `apiroute/testing/graphql_response.py` and returns an `httpx.Response`, which is a valid `ResponseSource`. `MockCall` gains a `graphql_variables` property that reads `variables` from a JSON body, or returns `None` when there isn't one.

## Risks / Trade-offs

- **[The built-in scanner disagrees with graphql-core on edge-case documents]** → It reads only operation headers. The tests feed both parsers the same fixtures, including strings and comments containing `$` and `(`.
- **[Automatic camelCase matching guesses wrong]** (`userID` vs `user_id`) → When it's ambiguous or there's no match, the class definition fails with a message suggesting `variables=`, so a wrong guess can't pass silently.
- **[Omitting `None` makes explicit null impossible through plain arguments]** → This is documented, and an escape hatch is listed in Open Questions.
- **[`expected=(200, 400)` treats a 400 without a GraphQL body as a decoder error rather than `UnexpectedResponse`]** → The decoder raises `UnexpectedResponse` itself when a 4xx body has no `errors`, so the exception type matches REST routes.
- **[Mutations that users want retried on read timeouts]** (idempotent mutations with client mutation IDs) → They can pass `idempotent=True` to `graphql_route` explicitly.
- **[Every operation is POST /graphql, so URL-based logging and redaction see one endpoint]** → `RequestSpec.operation` carries the name, and the docs point hooks at it.

## Migration Plan

This is purely additive. Existing routes get `idempotent=True`, which is today's behavior, and the emitters don't change, so generated clients regenerate identically. Release as `feat:` (minor). Rollback means reverting the commit, since nothing persists.

## Open Questions

- Should `idempotent=` also be exposed on `@route`, so REST POSTs get the same protection? It's useful, but it changes the public `@route` signature, so it's left to a separate change.
- An explicit-null escape hatch: a sentinel (`apiroute.graphql.NULL`) or a `Body`-annotated `variables` argument merged over the template. Pick one when implementing, or defer.
- Should `GraphQLError` with a throttling code feed `Retry-After`-style delays (Shopify's `extensions.cost`, GitHub's `RATE_LIMITED`)? Deferred until a real client needs it.
- Should `graphql_path` become a class config attribute (`CONFIG_ATTRIBUTES`) instead of a per-route `path=`? A per-route `path` plus `namespace()` covers it for now.
