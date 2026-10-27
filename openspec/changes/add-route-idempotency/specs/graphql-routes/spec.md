## MODIFIED Requirements

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
