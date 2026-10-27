## Context

`RouteExecutor._prepare()` builds the `RequestSpec` once per call, then `_should_retry(config, spec)` decides whether errors after sending may be retried: when the route's `RouteDefinition.idempotent` is true, or the request carries an idempotency key. Client hooks (`on_request`, `should_retry`, `check_response`) are plain methods a client or a `--base-class` overrides.

## Decisions

### 1. A hook on the client, not a class attribute

`Client.idempotent(self, request: RequestSpec) -> bool | None` returns `None` by default. `_should_retry` uses `self._root.idempotent(spec)` and falls back to `definition.idempotent` when that's `None`. A method can decide by operation name, method, path or anything else in the request.

*Alternative:* a class attribute listing operation names (`idempotent_operations = {...}`). Rejected because listing 30 of eBay's 74 Trading calls is brittle as the WSDL grows, while a rule like `startswith("Get")` follows it. A hook can still use a set if that's what fits.

### 2. The hook sees the request before `on_request`

It gets the spec as built, the same one `should_retry`'s caller has. `operation`, `method`, `url` and headers are all there. `on_request` changes run per attempt and can't change idempotency mid-call.

### 3. Idempotency keys are unchanged

`IdempotencyKey` still follows the route's own idempotency, decided in `RequestBuilder` before the hook runs. So:
- a route the hook marks safe may still carry the client's key, which is harmless;
- a route the hook marks unsafe gets no new key, because keys only go to routes that are non-idempotent by their own declaration, and isn't retried after sending. That's the safe outcome.

### 4. Reserved names

`RESERVED` lists attributes every generated client already has. It lacked `follow_redirects`, `idempotency_key`, `check_response`, `redact_url` and `soap_header`, which predate this change. With `idempotent` added, an operation by any of these names gets `unique()`'s suffix instead of shadowing the client's.

## Risks / Trade-offs

- **[A hook that answers True for an unsafe call]** → It's the user's declaration, as with `idempotent=True`. The README says to answer for reads only.
