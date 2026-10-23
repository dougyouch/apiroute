# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-23

The first release: a Python port of the Ruby gem
[client-api-builder](https://github.com/dougyouch/client-api-builder), with
connection handling separated from the API definition.

### Routes

- `@route` on a stub method, with the HTTP method inferred from its name;
  `{name}` and `:name` placeholders in paths, query and body templates; a
  whole-string `"{name}"` keeps the value's type
- Placeholders fall back to the client's attribute or method; `FROM_CLIENT`
  makes that explicit for a parameter
- Parameters no template uses must be annotated `Query`, `Header` or `Body`,
  or the class fails to build with `RouteDefinitionError`
- Routes without a `def` (`get_user = route("/users/:username")`) get a
  generated keyword-only signature
- `namespace()` blocks prefix the paths of the routes inside them
- Sections: nested `Section` classes reached as `client.<name>`, inheriting
  only what `inherit` lists
- `with_options()` for per-call headers, query, body (shallow-merged over a
  dict body), timeout, retries and return mode

### Responses

- Parsed JSON by default, or `returns="text" | "bytes" | "response"`
- `UnexpectedResponse` for unexpected statuses and invalid JSON
- Typed returns: a dataclass or pydantic model in the return annotation
  (or `model=`) converts the JSON; `ResponseValidationError` when it doesn't fit
- A keyword-only `Result` parameter turns the method body into a response hook
- Streaming to a file, a writable object or a chunk iterator, with the status
  checked before any of the body is read

### Sending requests

- Transports chosen per environment, not per class: one-shot (default),
  pooled, thread-local, or a caller-owned `httpx.Client`; fork-safe
- Async through `client.aio` on the same class, with async transports
  (one-shot, pooled per event loop, caller-owned) in a registry of their own
- Retries: attempts, backoff, cap, jitter and `Retry-After`; only network
  errors by default, `should_retry` to change that; every failure logged
- `on_request` (may change the request, e.g. to sign it) and `on_response`
  (with elapsed time) for every attempt

### Security

- `http`/`https`-only base URLs with a host; path values percent-encoded per
  segment; URLs joined rather than resolved; TLS verified by default
- Streamed file paths with a null byte or `..` segment rejected

[1.0.0]: https://github.com/dougyouch/apiroute/releases/tag/v1.0.0
