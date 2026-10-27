## Why

Since 2.0.0, only `GET`, `HEAD` and `OPTIONS` routes are retried after the request may have reached the server; other routes opt in with `route(..., idempotent=True)`. Generated clients can't do that, because their routes are generated and never edited. Upgrading ebay-apiroute to 2.1.0 showed the cost: all 74 Trading API operations are SOAP `POST`s, so about 30 read-only calls (`GetItem`, `GetOrders`, `VerifyAddItem`...) lost their read-timeout retries, and there's no way to give them back. `idempotency_key` only helps APIs that honor the header, and eBay's don't. Every SOAP client, and every API that reads with `POST`, has the same gap.

## What Changes

- **New `Client.idempotent(self, request) -> bool | None`** hook, overridable like `should_retry`. It gets the built `RequestSpec` (`operation`, `method`, `url`, headers), and its answer decides whether errors after sending may be retried. `None` (the default) keeps the route's own idempotency. A base class can then mark generated operations by name or method:

  ```python
  class TradingAuth(Client):
      def idempotent(self, request):
          return True if request.operation.startswith(("Get", "Verify")) else None
  ```
- **Idempotency keys keep following the route's own idempotency.** A route the hook marks idempotent still gets the client's key if it would otherwise have one, which is harmless.
- **The generator reserves `idempotent`**, along with `idempotency_key`, `follow_redirects`, `check_response`, `redact_url` and `soap_header`, which were missing. A generated operation with one of these names gets a suffixed name rather than shadowing the client's setting or hook.

## Capabilities

### New Capabilities
<!-- None. -->

### Modified Capabilities
- `route-idempotency`: adds the client hook that can override a route's idempotency per request.

## Impact

- **Changed:**
  - `Client` gains the `idempotent` hook;
  - `RouteExecutor._should_retry` consults it;
  - `codegen/python_names.RESERVED` gains six names;
  - the README documents the hook (Retries, and Methods to override).
- **Generated output:** unchanged unless an operation is named one of the newly reserved words.
- **Release:** `feat:` (minor).
