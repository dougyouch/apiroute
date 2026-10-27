## Context

A `graphql_route` compiles to one `RouteSpec` whose `body_format` is `GraphQLBody(document, operation_name)`. That turns the rendered variables into `{"query", "operationName", "variables"}`. `GraphQLDecoder` raises `GraphQLError` (with `.codes`) for a response with `errors`, on HTTP 200 or 400. `GraphQLRouteMethod.bind` returns the bound call, wrapped by `GraphQLPaginator` for `paginate=` routes, where each page is a call built by `page_call(cursor)`.

The APQ protocol (Apollo's, followed by other servers):
1. The client sends `extensions.persistedQuery = {"version": 1, "sha256Hash": "<hex sha256 of the query>"}` and no `query`.
2. A server that has the hash runs the query. One that doesn't answers an error with message `PersistedQueryNotFound` (`extensions.code` `PERSISTED_QUERY_NOT_FOUND`), usually on HTTP 200, sometimes 400.
3. The client resends with `query` and the extension. The server checks the hash, stores the query, and runs it.
4. A server without APQ answers `PersistedQueryNotSupported` (`PERSISTED_QUERY_NOT_SUPPORTED`). The client should send full queries from then on.

## Goals / Non-Goals

**Goals:**
- One flag, and the protocol is invisible to callers: one call in, one result or `GraphQLError` out, sync and async, paginated or not.
- Each attempt is an ordinary request, so retries, hooks and `with_options` behave as for any route, and `on_request` can see which kind of request it is.
- No global state that leaks between unrelated clients.

**Non-Goals:**
- GET for CDN caching, trusted documents and manifests, and `documentId` persisted documents.
- Sharing "this server has the hash" knowledge across calls. Every call starts hash-only, which is what APQ is for, and a miss costs one extra request.

## Decisions

### 1. Three compiled variants of the route, differing only in body format

For a persisted route, `GraphQLRouteMethod._spec_for` also builds two sibling `RouteMethod`s from the same function, each with the spec's `body_format` swapped (`RouteSpec._replace`):
- **hash:** `GraphQLBody(document, name, persisted="hash")` sends the extension and no `query`;
- **register:** `GraphQLBody(document, name, persisted="register")` sends `query` and the extension.

The route's own spec stays the full-document form, which is used once APQ is known to be unsupported. The variants are compiled with the same class and name, so argument binding, headers, retries and decoding are identical. The only difference is the bytes of the body.

*Alternative:* one `GraphQLBody` that reads its mode from a context variable set around each call. Rejected because hidden state flowing into a body encoder is harder to reason about and test than three plain routes, and context variables need care across async tasks.

*Alternative:* a body-option sentinel key that `GraphQLBody` strips. Rejected because it's a magic key in user-visible data.

### 2. `GraphQLPersistedCall` runs the protocol over the bound variants

`bind()` binds the three variants to the router with the same options, and returns a `GraphQLPersistedCall` (sync or async), which does the following:
1. If APQ is known unsupported for this client, it calls the full variant.
2. Otherwise it calls the hash variant. On a `GraphQLError` whose codes or messages show `PersistedQueryNotFound`, it calls the register variant once and returns that result.
3. On `PersistedQueryNotSupported`, it records the client as unsupported and calls the full variant.
4. Any other `GraphQLError` propagates.

Recognition checks `extensions.code` (`PERSISTED_QUERY_NOT_FOUND`, `PERSISTED_QUERY_NOT_SUPPORTED`) and the message (`PersistedQueryNotFound`, `PersistedQueryNotSupported`), since servers differ.

"Unsupported" is remembered per route and per root client instance, in a `weakref.WeakSet` on the route method. A client object pointing at a server without APQ pays one extra request per route, once. Another client, perhaps with another `base_url`, starts fresh, and nothing outlives the client.

### 3. Pagination composes underneath

`page_call(cursor)` builds each page's call through the same persisted binding, with the cursor body option merged. So every page is hash-first. The paginator doesn't know about persistence, and persistence doesn't know about pages.

### 4. The hash

`hashlib.sha256(document.encode("utf-8")).hexdigest()`, computed once per route over exactly the string `GraphQLBody` sends as `query`. Servers verify the hash against the query on registration, so they must match byte for byte.

### 5. Codegen flag

`--persisted-queries` sets `GraphQLOperationSpec.persisted = True` on every operation, and `DictClientEmitter` writes `persisted=True,` in the decorator. The document in the generated file is the one that's hashed, so generated clients and their servers agree.

### 6. Replies are classified where the context is known, and logged quietly

Only the hash-only variant's decoder (`GraphQLDecoder.for_persisted_replies()`) recognizes protocol replies, and it raises them as `PersistedQueryReply`, a `GraphQLError` subclass with a `kind`:
- **"not_found"** for `PersistedQueryNotFound`;
- **"not_supported"** for `PersistedQueryNotSupported`, **or any request error.** That's a response with errors and no `data` key, so nothing was executed.

`GraphQLPersistedCall` catches only `PersistedQueryReply`. Every other error, and every error from the register or full requests, propagates as a plain `GraphQLError`.

*Found testing against GitHub:* a server that doesn't implement APQ needn't answer `PersistedQueryNotSupported`. GitHub answers a hash-only request with *"A query attribute must be specified and must be a string."* and no `data`, and the first version raised that on every call. Treating any request error on a hash-only request as "not supported" covers such servers. If the full document then fails too, that real error raises loudly. The cost of a false positive (a server with APQ whose cached query fails validation) is only that this client sends full documents from then on, and the outcome is the same error.

`RetryPolicy` logs an exception at the level its `log_level` attribute names, else WARNING. `PersistedQueryReply.log_level` is DEBUG, so protocol replies stay in the logs without reading as failures. That's the follow-up this PR originally deferred.

## Risks / Trade-offs

- **[A miss costs a second request]** → That's inherent to APQ, and it's once per document per server cache lifetime.
- **[`on_request` hooks and mocks see two requests on a miss]** → This is documented. The body shows which is which (`query` absent or present), and `RequestSpec.operation` is the same for both.
- **[A server that answers the hash-only request with some other error]** → It propagates as a normal `GraphQLError`. apiroute doesn't guess.
- **[Retries]** → Each variant retries per the client's policy. A mutation's hash-only attempt is still non-idempotent, which is fine: a `PersistedQueryNotFound` means it didn't run.

## Tested against Apollo Server

With Apollo Server 4.11 running locally (APQ on by default, and a second instance with `persistedQueries: false`), from the server's own request log:
- A first call is a miss and a registration; later calls (sync and `.aio`) are hash-only. Apollo verifies the hash on registration, so its acceptance confirms the hashes match.
- A persisted, paginated route registers on the first page and sends every later page by hash.
- Against the server without APQ, one hash attempt is followed by full documents for that client; a new client tries once.
- `fetch-schema` of the server, then `generate graphql --persisted-queries` with an `@paginate` operation, gave a typed client that paged through every item the same way.

## Tested against GitHub

GitHub doesn't support APQ. With `persisted=True`, each route on each client makes one hash-only request, which GitHub refuses with a request error, then sends full documents, including every page of a paginated route (120 cpython issues). The only log lines are DEBUG.

## Open Questions

- Should a later change add GET for persisted queries (a CDN-cacheable `?extensions=...` request), with an option for the CSRF headers servers require (Apollo's `Apollo-Require-Preflight`)?
- Should codegen emit a manifest for trusted-document servers?
