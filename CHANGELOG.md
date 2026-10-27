# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [2.0.1](https://github.com/dougyouch/apiroute/compare/v2.0.0...v2.0.1) (2026-10-27)


### Documentation

* remove duplicated changelog entries and a stray user link ([b4963f6](https://github.com/dougyouch/apiroute/commit/b4963f69d31e95c476befd87d77611db892eb44d))

## [2.0.0](https://github.com/dougyouch/apiroute/compare/v1.12.0...v2.0.0) (2026-10-27)


### ⚠ BREAKING CHANGES

* POST, PUT, PATCH and DELETE routes, including generated OpenAPI POST operations and every SOAP operation, are no longer retried after a read timeout, write timeout, read/write error or remote protocol error. Declare idempotent=True on routes that are safe to repeat, or set idempotency_key on the client for APIs that support idempotency keys.

### Features

* retry only safe methods after the request may have reached the server ([68d9d8c](https://github.com/dougyouch/apiroute/commit/68d9d8c5e6ea78300d795bf56428741e76a86d1f))

## [1.12.0](https://github.com/dougyouch/apiroute/compare/v1.11.0...v1.12.0) (2026-10-27)


### Features

* send files in GraphQL variables as multipart requests ([aae7d90](https://github.com/dougyouch/apiroute/commit/aae7d90caa6dd3852167ed90294176a0a602b012))


### Bug Fixes

* read GraphQL Yoga's persisted-query misses, sent with HTTP 404 ([f355549](https://github.com/dougyouch/apiroute/commit/f355549a2f5d5e804d061530116454bc2b3e8eb9))

## [1.11.0](https://github.com/dougyouch/apiroute/compare/v1.10.0...v1.11.0) (2026-10-27)


### Features

* send GraphQL operations as automatic persisted queries ([9bb32c9](https://github.com/dougyouch/apiroute/commit/9bb32c96775efbcb63299c70a3e95f4605f6a640))


### Bug Fixes

* persisted queries work with servers that don't know the protocol, and log quietly ([32e5572](https://github.com/dougyouch/apiroute/commit/32e5572e7f6f9206024eb0e30ee8dd56a5bc2266))

## [1.10.0](https://github.com/dougyouch/apiroute/compare/v1.9.0...v1.10.0) (2026-10-27)


### Features

* iterate GraphQL connections across pages (paginate= and `@paginate`) ([b868545](https://github.com/dougyouch/apiroute/commit/b8685459568732ff453ea64606e6e63da3b9c553))

## [1.9.0](https://github.com/dougyouch/apiroute/compare/v1.8.0...v1.9.0) (2026-10-27)


### Features

* generate GraphQL clients from a schema and hand-written operations ([a11c804](https://github.com/dougyouch/apiroute/commit/a11c80480c86bc7b7bc2d12658473a4d4f00a53c))


### Bug Fixes

* **codegen:** give the same names whichever Python generates ([f750134](https://github.com/dougyouch/apiroute/commit/f750134c74eaa3b9860e06bd01b3a8c8d6f02d65))
* trust server GraphQL schemas, and read GitHub's error codes ([6eeb3e5](https://github.com/dougyouch/apiroute/commit/6eeb3e5c2d279a0ec082e3fb8d1fef96ce96bf14))


### Documentation

* propose apiroute generate graphql (OpenSpec change add-graphql-codegen) ([5004399](https://github.com/dougyouch/apiroute/commit/5004399020ad167db02cc7d5d2bc5fe6e7492cbc))

## [1.8.0](https://github.com/dougyouch/apiroute/compare/v1.7.0...v1.8.0) (2026-10-27)


### Features

* validate graphql_route documents against graphql_schema ([500f3e1](https://github.com/dougyouch/apiroute/commit/500f3e1be920cee2d0bbdc4834129a8273efa269))


### Bug Fixes

* read introspection from newer GraphQL servers on graphql-core 3.2 ([d33598c](https://github.com/dougyouch/apiroute/commit/d33598c19bf4e8a1d8585c116cbaf979c1b0737a))

## [1.7.0](https://github.com/dougyouch/apiroute/compare/v1.6.0...v1.7.0) (2026-10-27)


### Features

* add graphql_route for hand-written GraphQL operations ([ede15d0](https://github.com/dougyouch/apiroute/commit/ede15d038c51f691e9139d26b91186b9eebce7c3))

## [1.6.0](https://github.com/dougyouch/apiroute/compare/v1.5.1...v1.6.0) (2026-10-27)


### Features

* add apiroute.testing with MockTransport and a pytest plugin ([cecb862](https://github.com/dougyouch/apiroute/commit/cecb862e5b4ff27d94a8d0b1d90002017ce73cc7))

## [1.5.1](https://github.com/dougyouch/apiroute/compare/v1.5.0...v1.5.1) (2026-10-26)


### Bug Fixes

* keep a base_url's query string on the request ([31b6560](https://github.com/dougyouch/apiroute/commit/31b6560fa826bb05e1a4e968e8a088761bba461c))

## [1.5.0](https://github.com/dougyouch/apiroute/compare/v1.4.0...v1.5.0) (2026-10-26)


### Features

* follow_redirects client setting, sent with each request ([5272aa0](https://github.com/dougyouch/apiroute/commit/5272aa0ea8df648ac6bc87e45c6c86f4c836c998))

## [1.4.0](https://github.com/dougyouch/apiroute/compare/v1.3.0...v1.4.0) (2026-10-26)


### Features

* **codegen:** --base-url for specs with a relative server URL ([231fed4](https://github.com/dougyouch/apiroute/commit/231fed43993622ad3ac06013c7bda7dda071d3bf))
* **codegen:** --base-url, and sections inherit the client's retries and timeout ([e4190fe](https://github.com/dougyouch/apiroute/commit/e4190fef1cde96517364f591c8a544dfc0bdaea1))
* sections can inherit the client's retries and timeout ([e58c0e0](https://github.com/dougyouch/apiroute/commit/e58c0e0e3e0b0f30d3e526535bc08d24cd45b0fc))


### Bug Fixes

* **codegen:** don't repeat the API description in every section ([3fa8cdd](https://github.com/dougyouch/apiroute/commit/3fa8cdd9a6a80431fd23e37ad207366e5958f3c7))
* **codegen:** generated imports pass ruff in the consuming project ([f43f130](https://github.com/dougyouch/apiroute/commit/f43f130cf71b7be379ae8a948d315c130aea78e5))

## [1.3.0](https://github.com/dougyouch/apiroute/compare/v1.2.1...v1.3.0) (2026-10-26)


### Features

* check_response hook to reject a response inside the retry loop ([6732251](https://github.com/dougyouch/apiroute/commit/6732251971ce4f72be6d605d744e17c8cc2d91d5))
* mask secrets in URLs shown in errors and retry logs ([6732251](https://github.com/dougyouch/apiroute/commit/6732251971ce4f72be6d605d744e17c8cc2d91d5))

## [1.2.1](https://github.com/dougyouch/apiroute/compare/v1.2.0...v1.2.1) (2026-10-23)


### Documentation

* add AGENT.md, CLAUDE.md and the apiroute-client skill ([e435dc0](https://github.com/dougyouch/apiroute/commit/e435dc02c005d79fd970a661c0c556b7e9ed312b))
* make agent docs API-agnostic, with eBay only as an example ([1ae7b5b](https://github.com/dougyouch/apiroute/commit/1ae7b5b82913cdaede5afc1f35e65b0e4c7ea916))

## [1.2.0](https://github.com/dougyouch/apiroute/compare/v1.1.0...v1.2.0) (2026-10-23)


### Features

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
