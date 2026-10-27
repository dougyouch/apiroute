## 1. Hook

- [x] 1.1 `Client.idempotent(self, request) -> bool | None`, returning `None`
- [x] 1.2 `RouteExecutor._should_retry` consults the root client's hook before the route's own idempotency
- [x] 1.3 Tests: every scenario under "A client can decide idempotency per request", sync and async, including with an idempotency key

## 2. Reserved names

- [x] 2.1 Add `idempotent`, `idempotency_key`, `follow_redirects`, `check_response`, `redact_url` and `soap_header` to `RESERVED`
- [x] 2.2 Test: an operation named `idempotent` gets `idempotent_2`

## 3. Fix shipped with it

- [x] 3.1 Model indexes with no models write `__all__: list[str] = []` (mypy 1.x can't infer an empty list), with a fixture spec that has no models, and mypy over it in the typing tests

## 4. Docs and checks

- [x] 4.1 README: the hook in Retries and in Methods to override
- [x] 4.2 Ruff, the full suite (with the exit code checked), the lowest-dependencies run, and `openspec validate --all --strict`
