## Why

Every `@route` retries timeouts, network errors and protocol errors, including errors that happen after the server may already have received the request: a read timeout, a dropped connection mid-response. For a `GET`, retrying is harmless. For a `POST` that creates an order, charges a card or sends a message, it can do the thing twice. Since 1.7.0, GraphQL mutations are protected from this (`RouteSpec.idempotent`), but REST routes aren't. The safe default is to retry such errors only for methods that don't change anything, and to let routes opt in. Some APIs make retrying safe another way: Stripe, Adyen, PayPal and Square accept an `Idempotency-Key` header, an IETF draft standard, and run a request with a key they've already seen only once. apiroute should send one key per call and reuse it on every retry.

## What Changes

- **BREAKING (retry behavior): non-GET routes aren't retried after the request may have reached the server.** `GET`, `HEAD` and `OPTIONS` routes are idempotent by default. `POST`, `PUT`, `PATCH` and `DELETE` routes are not, unless declared `idempotent=True`. For a non-idempotent route, read and write timeouts, read and write errors, and remote protocol errors aren't retried, whatever `should_retry` says. Errors before anything was sent (connect errors and timeouts, pool timeouts) and HTTP responses (429, 503 and the like, through `should_retry`) are retried as before. This applies to every route, including generated OpenAPI and WSDL clients, which are mostly POST.
- **`route(..., idempotent=True|False)`** overrides the method's default. `graphql_route` is unchanged: queries are idempotent and mutations aren't, as before.
- **Idempotency keys:**
  - `route(..., idempotency_key="Idempotency-Key")` sends that header with a fresh UUID4 per call, the same value on every retry of that call. Such a route is retried like an idempotent one.
  - A `Client` or `Section` setting, `idempotency_key = "Idempotency-Key"`, does this for every non-idempotent route. That's how a generated client opts in from its base class. A section uses its parent's unless it sets its own.
  - `idempotency_key=False` on a route turns the class setting off for that route.
  - A key the caller already sent (`with_options(headers={"Idempotency-Key": ...})`) is kept.

## Capabilities

### New Capabilities
- `route-idempotency`: which routes retry after the request may have reached the server, and idempotency-key headers that make retrying safe.

### Modified Capabilities
- `graphql-routes`: the "Mutations are not retried after the request may have reached the server" requirement said existing `@route` methods keep their retry behavior. They now follow their HTTP method.

## Impact

- **Runtime:**
  - `RouteSpec`/`RouteDefinition.idempotent` becomes optional (`None` means "by method"), resolved by `RouteCompiler`;
  - `route()` gains `idempotent` and `idempotency_key`;
  - `ClientConfig` gains `idempotency_key`, which sections take from their parent;
  - a new `IdempotencyKey` decides the header for a call, used by `RequestBuilder` (which adds it) and `RouteExecutor` (which retries such routes like idempotent ones).
- **Behavior change for existing users:** POST, PUT, PATCH and DELETE routes, including SOAP operations and generated POST endpoints, no longer retry read timeouts and similar errors. Routes that should can say `idempotent=True`, or the client can set `idempotency_key`. Errors before sending and HTTP responses still retry.
- **Release:** the behavior change is called out in the changelog. Whether it's released as a major version is the maintainer's call; see the design's open question.
