## Context

`RouteSpec` and `RouteDefinition` have `idempotent: bool = True`. `RouteExecutor._should_retry()` wraps the client's `should_retry` in `UnsentRetryFilter` when a route isn't idempotent, so errors in `MAY_HAVE_BEEN_SENT` (`ReadTimeout`, `WriteTimeout`, `ReadError`, `WriteError`, `RemoteProtocolError`) aren't retried. Only `graphql_route` sets it today, to `False` for mutations. `RequestBuilder.build()` makes the `RequestSpec` once per call, before the retry loop, and every attempt sends it, after `on_request`. `ClientConfig` holds class settings; sections take `base_url` and `follow_redirects` from their parent unless they set their own.

## Goals / Non-Goals

**Goals:**
- Safe by default: only `GET`, `HEAD` and `OPTIONS` are retried after the request may have been sent, unless a route says otherwise.
- One switch per route (`idempotent=`), and one per client for idempotency keys.
- A key is generated once per call and is identical on every attempt, so the server can tell retries apart from new requests.

**Non-Goals:**
- Changing what's retried before sending, or how HTTP responses are retried (`should_retry`).
- Key formats other than UUID4, or keys derived from the request body.
- Codegen changes. OpenAPI specs rarely say which operations are safe to repeat, so generated routes follow their method, and a base class can set `idempotency_key`.

## Decisions

### 1. The default comes from the method: GET, HEAD and OPTIONS only

`RouteSpec.idempotent` becomes `bool | None = None`. `RouteCompiler` resolves `None` to `http_method in {"GET", "HEAD", "OPTIONS"}`, and `RouteDefinition.idempotent` is always a bool. `graphql_route` keeps passing an explicit bool, so GraphQL behavior is unchanged.

PUT and DELETE are idempotent in HTTP's definition, but they're excluded on purpose. Real APIs often implement them with side effects that aren't safe to repeat, such as a PUT that appends or a DELETE that decrements, so they need an explicit `idempotent=True`. This is the maintainer's decision for this change.

*Alternative:* keep "everything retries" and make `idempotent=False` opt-in. Rejected: unsafe by default, and the people who most need protection are the least likely to know they need it.

### 2. Idempotency keys: route-level header name, class-level default

`IdempotencyKey(definition, config)` answers two questions:
- `header_name`: the header to send, or `None`. It's the route's `idempotency_key` when that's a string; `None` when the route says `False`; otherwise the class's `idempotency_key`, but only for non-idempotent routes. Idempotent routes don't need a key.
- `makes_retry_safe`: whether a header will be sent.

`RequestBuilder` adds `{header_name: str(uuid.uuid4())}` to the headers when the name is set, unless the built headers already have that header (case-insensitively), from the caller's `with_options` or a route template. Because `build()` runs once per call, every attempt carries the same key. `on_request` hooks see it.

`RouteExecutor` treats a route as idempotent when `definition.idempotent` or `IdempotencyKey(...).makes_retry_safe`, so keyed POSTs keep full retries.

`ClientConfig.idempotency_key: str | None = None` is a class setting. Sections take their parent's unless they set their own (`explicit`), like `follow_redirects`, because it's a property of the API.

*Alternative:* generate the key in `on_request`. Rejected: that runs per attempt, so each retry would get a new key, which defeats the purpose.

### 3. What stays the same

- **Errors before sending** (`ConnectError`, `ConnectTimeout`, `PoolTimeout`) are retried for every route. Nothing reached the server.
- **HTTP responses** are offered to `should_retry` as before. A 429 or 503 means the server didn't do the work, and retrying them is already the user's explicit choice.
- **`with_options(retries=...)`** still sets the number of attempts. It doesn't change which errors are retried.

## Risks / Trade-offs

- **[Behavior change: POST, PUT, PATCH and DELETE routes stop retrying read timeouts]** This includes SOAP operations, which are all POST, and APIs that use POST for reads → It's called out in the changelog and README. `idempotent=True` per route, or `idempotency_key` on the client, restores retries where they're safe. Errors before sending and 5xx/429 retries are unaffected.
- **[Generated clients can't mark single routes]** → A base class can set `idempotency_key`, or override `should_retry` for response errors. Per-operation marking in codegen can come later if a spec format offers the information.
- **[A server that ignores Idempotency-Key]** → The header is opt-in. Users set it only for APIs that honour it, and it's documented as such.

## Open Questions

- **Major or minor?** Retrying less after a read timeout is safer, but it's observable. Users who relied on POST retries will see more errors. Release as `feat!:` (2.0.0) or as `feat:` with a prominent changelog note? This is decided by the commit message when merging.
