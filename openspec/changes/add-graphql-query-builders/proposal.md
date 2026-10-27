## Why

`graphql_route` takes a document written ahead of time, so each operation has one selection set. That suits a service with a known set of operations. It suits a shared client less: `et-gateway-client`, used by many EverTrue services against one federated supergraph, is generated with `ariadne-codegen` so each call can pick its own fields (`Query.cadence(id=...).fields(CadenceSchemaFields.name)`) and a field that doesn't exist fails when the query is built. Its generated builders run to about 34k lines across `custom_fields.py`, `custom_queries.py` and `input_types.py`.

An audit of that client's transport layer found no retries, no mock transport and no `GraphQLError`-style error codes. The `format_error` helper in its `errors.py` exists because the generated `__str__` drops `extensions` and `path`. Those are things apiroute already provides, but only for routes declared when the class is created. apiroute has no way to send a document chosen at call time (none found in `src/apiroute/graphql` or the README).

This is a proposal to discuss, not a committed design.

## What Changes

Opt-in, in three steps. The first is useful alone and tells us whether the others are wanted.

- **A call-time entry point**, something like `client.graphql(document, variables=...)`. It reuses the variable binder, decoder, `GraphQLError`, retries and operation-name hooks, so `mock.on(operation=...)` and `on_request` work as they do for routes. Queries retry like a `GET`; a mutation isn't re-sent after an error that may have happened once the server had the request.
- **Generated field selectors**, behind a flag such as `apiroute generate graphql --builders`. They would be emitted per type from the schema and render to a document for the entry point above. To limit size, restrict them to the types reachable from chosen root fields.
- **Models for dynamic selections.** Today's models follow the selections you wrote, so they are static. A per-call selection needs either models built at runtime from the selection, or a model whose unfetched fields raise instead of returning `None`. This is the open design question and should be settled before step 2.

`graphql_route` and `apiroute generate graphql` with hand-written `.graphql` operations stay as they are.

## Alternatives considered

- **Adopt `ariadne-codegen` in apiroute.** Rejected. It would replace an operation-first generator that already validates against the schema and generates models, pagination, uploads and persisted queries. Downstream repositories regenerate with each apiroute release, so output would follow ariadne's release cadence.
- **Treat ariadne as a consumer instead.** `ariadne-codegen` can substitute its generated base client (`base_client_file_path`; not yet checked against `et-gateway-client`'s config). An apiroute-backed base client would give it retries, mutation-safe re-sending and error codes, and costs a shim to maintain. This is the fallback if the builders aren't pursued.

## Capabilities

### New Capabilities
- `graphql-query-builders`: call-time GraphQL execution and, later, generated field selectors.

### Modified Capabilities
<!-- None yet. Step 3 may touch `graphql-codegen`. -->

## Impact

- **Tradeoffs:**
  - builder output is generated code that downstream repositories regenerate, so emitter changes need cover in `tests/codegen/`;
  - the codebase and README would document two ways to express an operation;
  - per-call selections skip the check `graphql_route` runs when the class is created, so they rely on build-time field checks.
- **Dependencies:** none new. graphql-core and pydantic stay optional extras.
- **Release:** `feat:` (minor) for each step.
- **Open:** whether `RouteExecutor`'s retry and decode code can run without a declared route; this decides how small step 1 is.
