## ADDED Requirements

### Requirement: Only safe methods retry after the request may have been sent
A route's idempotency SHALL default from its HTTP method: `GET`, `HEAD` and `OPTIONS` idempotent, and every other method (`POST`, `PUT`, `PATCH`, `DELETE`) not. `route(..., idempotent=True|False)` SHALL override the default. For a non-idempotent route, errors that may occur after the request was sent (read and write timeouts, read and write errors, remote protocol errors) SHALL NOT be retried, whatever `should_retry` returns. Errors before sending (connect errors, connect timeouts, pool timeouts) and HTTP responses SHALL still be offered to `should_retry`, for every route.

#### Scenario: GET read timeout
- **WHEN** a client with `retries = Retries(attempts=3)` calls a `GET` route and the first attempt raises `httpx.ReadTimeout`
- **THEN** the request is retried

#### Scenario: POST read timeout
- **WHEN** the same client calls a `POST` route and the first attempt raises `httpx.ReadTimeout`
- **THEN** the call raises after one attempt

#### Scenario: PUT and DELETE need opting in
- **WHEN** a `PUT` route and a `DELETE` route without `idempotent=` each get `httpx.ReadTimeout`
- **THEN** neither is retried

#### Scenario: Declared idempotent
- **WHEN** a `POST` route is declared `idempotent=True` and gets `httpx.ReadTimeout`
- **THEN** it's retried

#### Scenario: Declared not idempotent
- **WHEN** a `GET` route is declared `idempotent=False` and gets `httpx.ReadTimeout`
- **THEN** it isn't retried

#### Scenario: POST connect error
- **WHEN** a `POST` route's first attempt raises `httpx.ConnectError`
- **THEN** it's retried

#### Scenario: POST and a retried status
- **WHEN** a client whose `should_retry` retries 503 calls a `POST` route answered 503 then 200
- **THEN** it's retried and returns the 200's result

### Requirement: Idempotency keys make retries safe
`route(..., idempotency_key="Header-Name")` SHALL send that header with a new UUID4 for each call, the same value on every attempt of that call, and such a route SHALL be retried like an idempotent one. A `Client` or `Section` class attribute `idempotency_key = "Header-Name"` SHALL do the same for each of its non-idempotent routes. A section SHALL use its parent's value unless it sets its own. `idempotency_key=False` on a route SHALL turn the class setting off for it. Idempotent routes SHALL NOT get the class's key. A key header the request already has (from `with_options(headers=...)` or the route's headers) SHALL be kept.

#### Scenario: One key per call, the same on retries
- **WHEN** a `POST` route with `idempotency_key="Idempotency-Key"` gets `httpx.ReadTimeout` and then a 200
- **THEN** it's retried, and both attempts carry the same `Idempotency-Key` value

#### Scenario: A new key per call
- **WHEN** the route is called twice
- **THEN** the two calls carry different keys

#### Scenario: Class setting
- **WHEN** a client sets `idempotency_key = "Idempotency-Key"`
- **THEN** its `POST` routes and its sections' `POST` routes send a key and are retried after a read timeout, and its `GET` routes send none

#### Scenario: Turned off for one route
- **WHEN** the client sets `idempotency_key` and a `POST` route says `idempotency_key=False`
- **THEN** that route sends no key and isn't retried after a read timeout

#### Scenario: The caller's own key
- **WHEN** a call is made with `with_options(headers={"Idempotency-Key": "mine"})`
- **THEN** the request carries `mine`
