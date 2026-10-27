## 1. Idempotency by method

- [x] 1.1 `RouteSpec.idempotent: bool | None = None`; `RouteCompiler` resolves `None` from the method (GET, HEAD, OPTIONS)
- [x] 1.2 `route(..., idempotent=)`, documented in its docstring
- [x] 1.3 Tests: every scenario under "Only safe methods retry" (GET, POST, PUT, DELETE, declared either way, connect error, 503 through `should_retry`), sync and async; GraphQL query and mutation behavior unchanged

## 2. Idempotency keys

- [x] 2.1 `ClientConfig.idempotency_key` (validated as a non-empty string or None; sections take the parent's unless set)
- [x] 2.2 `route(..., idempotency_key=)` (a header name or False), carried on `RouteSpec` and `RouteDefinition`
- [x] 2.3 `IdempotencyKey`: the header name for a definition and config; `RequestBuilder` adds a UUID4 unless the header is present; `RouteExecutor` treats keyed routes as idempotent
- [x] 2.4 Tests: every scenario under "Idempotency keys make retries safe", including sections, async, and `on_request` seeing the key

## 3. Docs and checks

- [x] 3.1 README: the Retries section (what's retried for which methods, `idempotent=`, `idempotency_key`), the behavior change, and SOAP and generated clients
- [x] 3.2 Ruff, the full suite (with the exit code checked), the lowest-dependencies run, and `openspec validate --all --strict`
