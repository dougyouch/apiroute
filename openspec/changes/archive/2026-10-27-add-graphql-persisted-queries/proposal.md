## Why

A GraphQL operation is sent in full on every call. Real operations are large: the GitHub operations used to test 1.9.0 and 1.10.0 run 400–900 bytes each, and production clients send multi-kilobyte documents thousands of times. Automatic persisted queries (APQ) send a SHA-256 hash of the document instead. The server answers from its cache, and only on a miss does the client send the document once to register it. APQ is supported by Apollo Server, GraphQL Yoga (plugin), Hasura, AWS AppSync and others, and clients such as Apollo Client and urql implement it. apiroute already knows each route's exact document, so it can do this transparently.

## What Changes

- **`graphql_route(..., persisted=True)`** sends each call as `{"operationName", "variables", "extensions": {"persistedQuery": {"version": 1, "sha256Hash": ...}}}`, without `query`.
  - **On a miss** (`PersistedQueryNotFound`), it retries once with the document and the hash together, which registers it. Later calls send only the hash again.
  - **When the server doesn't support APQ** (`PersistedQueryNotSupported`), that client stops trying for that route and sends full documents from then on.
  - Both protocol replies are handled inside the call, so callers see one call, one result, and the usual `GraphQLError` for real errors.
- **The hash** is the lowercase hex SHA-256 of the exact document string the route sends, computed once.
- **Composes with `paginate=`:** every page uses persisted queries.
- **`apiroute generate graphql --persisted-queries`** generates every route with `persisted=True`. Without the flag, generated output is unchanged.

Not in scope: GET requests for CDN caching (which needs per-server CSRF headers), trusted-document allowlists and manifest files, and `documentId`-style persisted documents from the GraphQL-over-HTTP proposal.

## Capabilities

### New Capabilities
- `graphql-persisted-queries`: sending GraphQL operations by hash with automatic registration (APQ), at run time and in generated clients.

### Modified Capabilities
<!-- None: existing GraphQL requirements are unchanged; persisted queries are opt-in. -->

## Impact

- **Runtime:**
  - `GraphQLBody` gains hash-only and register modes;
  - `GraphQLRouteBuilder` builds the variant specs;
  - `GraphQLRouteMethod` compiles and binds them, with a new `GraphQLPersistedCall` doing the miss and unsupported handling;
  - `graphql_route` and `GraphQLRouteOptions` gain `persisted`.
- **Codegen:** the CLI flag, `GraphQLOperationSpec.persisted`, and `DictClientEmitter` writing `persisted=True`.
- **No new dependencies.** `hashlib` is in the standard library.
- **Release:** `feat:` (minor).
