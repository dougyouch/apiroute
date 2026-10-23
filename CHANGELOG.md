# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [1.2.0](https://github.com/dougyouch/apiroute/compare/v1.1.0...v1.2.0) (2026-10-23)


### Features

* auth base classes for generated clients, operation names and SOAP headers ([feab2db](https://github.com/dougyouch/apiroute/commit/feab2db9de25cd8349842947349a68612c33ec15))
* auth base classes for generated clients, operation names and SOAP headers ([2313b19](https://github.com/dougyouch/apiroute/commit/2313b19768a36b0301b84ee27c678e9f9ef76055))
* **codegen:** plain-text docstrings from HTML spec descriptions ([6ca25d9](https://github.com/dougyouch/apiroute/commit/6ca25d99efcd7473e8a8ff049abf870cf25a009e))


### Bug Fixes

* **codegen:** skip Content-Type, Accept and Authorization header parameters ([879698e](https://github.com/dougyouch/apiroute/commit/879698e3e1b08c342def9a1613cf01bb22aa41bd))

## [1.1.0](https://github.com/dougyouch/apiroute/compare/v1.0.0...v1.1.0) (2026-10-23)


### Features

* **codegen:** generate layered client packages from OpenAPI and Swagger specs ([e6e078b](https://github.com/dougyouch/apiroute/commit/e6e078b0229e73b13fdac68796d4c9e17fd19352))
* **codegen:** generate layered clients from OpenAPI/Swagger specs and WSDLs ([ba7392e](https://github.com/dougyouch/apiroute/commit/ba7392e6d64fbbf8b546007c2078dfb29d8a8662))
* **codegen:** generate SOAP clients from WSDL documents ([df609ec](https://github.com/dougyouch/apiroute/commit/df609ec733216da96dbfbc9b63ec8cd1d28ee29c))
* lazy route compilation, lazy attributes, typed clients and route headers ([7c5b71b](https://github.com/dougyouch/apiroute/commit/7c5b71b5635359e09fd8a84f1afde685204267f9))
* per-route body_format and a multipart body format ([8d5a3c4](https://github.com/dougyouch/apiroute/commit/8d5a3c48e4884bbaff1bd8db20a11e2bd3273c9c))

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
